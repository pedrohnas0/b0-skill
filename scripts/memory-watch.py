#!/usr/bin/env python3
"""Auto-commit .memory changes via event bus.

Flow:
  1. Detect file changes in ~/dev/.memory/ (watchdog)
  2. Debounce 10s
  3. Gate call to Vercel (auth + tokens)
  4. Publish memory.changed to QStash → Worker
  5. Worker generates commit message, publishes memory.commit-ready → Daemon
  6. Daemon receives commit-ready via HTTP, does git commit + push

Fallback: if commit-ready doesn't arrive in 60s, commit with generic message.
"""

import time
import subprocess
import os
import sys
import json
import hmac
import hashlib
import base64
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import requests
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Missing deps: apt install python3-watchdog python3-requests", file=sys.stderr)
    sys.exit(1)

# --- Config ---

MEMORY_DIR = Path.home() / "dev" / ".memory"
DEBOUNCE_SEC = 10
COMMIT_READY_TIMEOUT = 60
HTTP_PORT = 8787


def load_env():
    env_file = Path.home() / "dev" / ".claude" / "skills" / "b0-skill" / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


dotenv = load_env()
AI_URL = os.environ.get("LAB_AI_URL", dotenv.get("LAB_AI_URL", ""))
API_KEY = os.environ.get("B0_API_KEY", dotenv.get("B0_API_KEY", ""))
QSTASH_TOKEN = os.environ.get("QSTASH_TOKEN", dotenv.get("QSTASH_TOKEN", ""))
QSTASH_CURRENT_SIGNING_KEY = os.environ.get(
    "QSTASH_CURRENT_SIGNING_KEY", dotenv.get("QSTASH_CURRENT_SIGNING_KEY", "")
)
QSTASH_NEXT_SIGNING_KEY = os.environ.get(
    "QSTASH_NEXT_SIGNING_KEY", dotenv.get("QSTASH_NEXT_SIGNING_KEY", "")
)
WORKER_URL = os.environ.get("WORKER_URL", dotenv.get("WORKER_URL", ""))

# Shared state for commit-ready events
commit_ready_lock = threading.Lock()
commit_ready_event = threading.Event()
commit_ready_message = {"message": None, "files": None}


# --- QStash signature verification ---


def b64url_decode(s):
    """Decode base64url with proper padding."""
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_qstash_signature(signature, body_bytes):
    """Verify QStash JWT signature (HMAC-SHA256)."""
    if not signature:
        return False

    parts = signature.split(".")
    if len(parts) != 3:
        return False

    header_b64, payload_b64, sig_b64 = parts

    for key in [QSTASH_CURRENT_SIGNING_KEY, QSTASH_NEXT_SIGNING_KEY]:
        if not key:
            continue
        try:
            # HMAC-SHA256 over "header.payload"
            msg = f"{header_b64}.{payload_b64}".encode("utf-8")
            expected = hmac.new(key.encode("utf-8"), msg, hashlib.sha256).digest()
            actual = b64url_decode(sig_b64)

            if hmac.compare_digest(expected, actual):
                return True
        except Exception:
            continue

    return False


# --- HTTP Server ---


class DaemonHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default access logs
        pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "watching": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/events/commit-ready":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)

            # Verify QStash signature
            signature = self.headers.get("Upstash-Signature", "")
            if not verify_qstash_signature(signature, body_bytes):
                print("  commit-ready: invalid signature", file=sys.stderr)
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized")
                return

            try:
                event = json.loads(body_bytes)
                message = event.get("message", "")
                files = event.get("files", [])

                if message:
                    with commit_ready_lock:
                        commit_ready_message["message"] = message
                        commit_ready_message["files"] = files
                    commit_ready_event.set()
                    print(f"  commit-ready received: {message}")

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            except Exception as e:
                print(f"  commit-ready parse error: {e}", file=sys.stderr)
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"bad request")
        else:
            self.send_response(404)
            self.end_headers()


def start_http_server():
    server = HTTPServer(("0.0.0.0", HTTP_PORT), DaemonHandler)
    print(f"  HTTP server on :{HTTP_PORT}")
    server.serve_forever()


# --- File watcher ---


class Handler(FileSystemEventHandler):
    def __init__(self):
        self.pending = False
        self.last_event = 0.0

    def on_any_event(self, event):
        if event.is_directory:
            return
        if ".git" in str(event.src_path):
            return
        self.pending = True
        self.last_event = time.time()


def git(*args):
    result = subprocess.run(
        ["git", "-C", str(MEMORY_DIR)] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


def get_diff():
    git("add", "-A")
    result = git("diff", "--cached")
    return result.stdout.strip()


def get_changed_files():
    result = git("diff", "--cached", "--name-only")
    return result.stdout.strip()


def get_gate_tokens():
    """Call Vercel gate to get auth tokens."""
    if not AI_URL or not API_KEY:
        return None

    try:
        res = requests.post(
            f"{AI_URL}/api/chat",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={"message": "noop"},
            timeout=15,
        )
        if res.status_code != 200:
            print(f"  gate failed: {res.status_code}", file=sys.stderr)
            return None
        return res.json()
    except Exception as e:
        print(f"  gate error: {e}", file=sys.stderr)
        return None


def publish_memory_changed(diff, files, gate):
    """Publish memory.changed event to QStash → Worker."""
    if not QSTASH_TOKEN or not WORKER_URL:
        print("  QSTASH_TOKEN or WORKER_URL not set, skipping bus", file=sys.stderr)
        return False

    try:
        res = requests.post(
            f"https://qstash.upstash.io/v2/publish/{WORKER_URL}/events/memory-changed",
            headers={
                "Authorization": f"Bearer {QSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "type": "memory.changed",
                "diff": diff[:4000],
                "files": files.split("\n") if files else [],
                "sessionToken": gate["sessionToken"],
                "accessToken": gate["accessToken"],
            },
            timeout=15,
        )
        if res.status_code in (200, 201, 202):
            print("  memory.changed published to QStash")
            return True
        else:
            print(
                f"  QStash publish failed: {res.status_code} {res.text[:100]}",
                file=sys.stderr,
            )
            return False
    except Exception as e:
        print(f"  QStash publish error: {e}", file=sys.stderr)
        return False


def commit_and_push(message):
    result = git("commit", "-m", message)
    if result.returncode != 0:
        print(f"  commit failed: {result.stderr}", file=sys.stderr)
        return False
    push = git("push")
    if push.returncode != 0:
        print(f"  push failed: {push.stderr}", file=sys.stderr)
        return False
    return True


def main():
    if not MEMORY_DIR.exists():
        print(f"Memory dir not found: {MEMORY_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Watching {MEMORY_DIR} (debounce {DEBOUNCE_SEC}s)")
    if not API_KEY:
        print(
            "  WARNING: B0_API_KEY not set, will use fallback messages",
            file=sys.stderr,
        )
    if not QSTASH_TOKEN:
        print("  WARNING: QSTASH_TOKEN not set, bus disabled", file=sys.stderr)

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    handler = Handler()
    observer = Observer()
    observer.schedule(handler, str(MEMORY_DIR), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(2)

            if not handler.pending:
                continue
            if time.time() - handler.last_event < DEBOUNCE_SEC:
                continue

            handler.pending = False

            diff = get_diff()
            if not diff:
                continue

            files = get_changed_files()
            print(f"  changed: {files[:80]}")

            # Reset commit-ready state
            commit_ready_event.clear()
            with commit_ready_lock:
                commit_ready_message["message"] = None
                commit_ready_message["files"] = None

            # Get gate tokens
            gate = get_gate_tokens()
            if not gate:
                # Fallback: commit with generic message
                short_files = files.replace("\n", ", ")[:50]
                message = f"auto: update {short_files}"
                print(f"  commit (fallback, no gate): {message}")
                commit_and_push(message)
                continue

            # Publish to bus
            published = publish_memory_changed(diff, files, gate)

            if published:
                # Wait for commit-ready from bus
                print(f"  waiting for commit-ready ({COMMIT_READY_TIMEOUT}s timeout)...")
                arrived = commit_ready_event.wait(timeout=COMMIT_READY_TIMEOUT)

                if arrived:
                    with commit_ready_lock:
                        message = commit_ready_message["message"]
                else:
                    print("  commit-ready timeout, using fallback")
                    message = None
            else:
                message = None

            # Fallback if bus failed
            if not message:
                short_files = files.replace("\n", ", ")[:50]
                message = f"auto: update {short_files}"

            print(f"  commit: {message}")
            if commit_and_push(message):
                print("  pushed ok")
            else:
                print("  push failed", file=sys.stderr)

    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
