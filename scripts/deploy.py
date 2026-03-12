#!/usr/bin/env python3
"""deploy — test, deploy, and verify buildzero services.

Usage:
  deploy                    full pipeline (test → deploy → verify)
  deploy auth ai-worker     deploy specific services only
  deploy --no-test          skip unit tests
  deploy --dry-run          show plan without executing
"""

import subprocess
import sys
import os
import re
import time
import threading
import urllib.request
import json
from pathlib import Path

SCRIPTS_DIR = Path("/home/pedro/dev/.claude/skills/b0-skill/scripts")
sys.path.insert(0, str(SCRIPTS_DIR))
import ui

BUILDZERO = Path.home() / "dev" / "buildzero"
ENV_FILE = Path("/home/pedro/dev/.claude/skills/b0-skill/.env")

DEPLOY_ORDER = ["auth", "ai", "ai-worker", "telegram", "web"]

SERVICES = {
    "auth":      {"type": "vercel",  "path": "services/auth"},
    "ai":        {"type": "vercel",  "path": "services/ai"},
    "ai-worker": {"type": "worker",  "path": "services/ai-worker"},
    "telegram":  {"type": "worker",  "path": "services/telegram"},
    "web":       {"type": "vercel",  "path": "services/web"},
}

HEALTH_URLS = {
    "auth":      "https://auth-lilac-five-97.vercel.app/api/health",
    "ai":        "https://ai-three-pi.vercel.app/api/health",
    "ai-worker": "https://b0-ai-worker.pedrohnas0.workers.dev/health",
    "telegram":  "https://b0-telegram.pedrohnas0.workers.dev/health",
    "web":       "https://web-blond-psi-94.vercel.app",
}

# Phases worth showing — skip noise like "starting...", "retrieving..."
SHOW_PHASES = {
    "building...", "installing deps...", "deploying...", "finishing...",
    "uploading...", "uploaded", "finalizing...",
}


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def run_cmd(cmd, cwd=None, extra_env=None, timeout=300):
    merged = {**os.environ, **(extra_env or {})}
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, env=merged,
        )
        duration = time.monotonic() - start
        return proc.returncode == 0, proc.stdout + proc.stderr, duration
    except subprocess.TimeoutExpired:
        return False, "timeout", time.monotonic() - start
    except Exception as e:
        return False, str(e), time.monotonic() - start


def fmt_t(secs):
    return f"{int(secs * 1000)}ms" if secs < 1 else f"{secs:.1f}s"


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def parse_phase(line):
    """Extract deploy phase from CLI output line."""
    clean = strip_ansi(line).strip()
    if not clean:
        return None
    # Vercel
    if "Retrieving project" in clean: return "retrieving..."
    if clean.startswith("Uploading"):  return "uploading..."
    if "Installing" in clean:          return "installing deps..."
    if "Build Completed" in clean:     return "build complete"
    if "Deploying outputs" in clean:   return "deploying..."
    if "Completing" in clean:          return "finishing..."
    if "Aliased:" in clean:            return "done"
    if "Building:" in clean:
        if "error TS" in clean:        return "TS warning"
        return "building..."
    if "Building..." in clean:         return "building..."
    # Wrangler
    if "Total Upload" in clean:        return "uploading..."
    if clean.startswith("Uploaded"):   return "uploaded"
    if clean.startswith("Deployed"):   return "finalizing..."
    return None


# ── Test ──────────────────────────────────────────────

def phase_test():
    ui.group_start("test")

    ok, output, _ = run_cmd(
        ["bun", "scripts/test.ts", "-q"],
        cwd=str(BUILDZERO), timeout=120,
    )

    clean = strip_ansi(output)

    for m in re.finditer(
        r"\s*[✓✗]\s+([a-z][\w-]*)\s+(\d+)\s+pass\s+(\d+)\s+fail\s+\((.+?)\)",
        clean,
    ):
        name, passed, failed, t = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        if failed == 0:
            ui.item_ok(name, f"{passed} pass", t)
        else:
            ui.item_fail(name, f"{passed} pass, {failed} fail", t)

    if not ok:
        for line in clean.splitlines():
            stripped = line.strip()
            if "error:" in stripped.lower():
                print(f"  {ui.dim('│')}       {ui.dim(stripped[:120])}")
        return False

    return True


# ── Deploy ────────────────────────────────────────────

class ServiceState:
    def __init__(self, name):
        self.name = name
        self.phase = "queued"
        self.done = False
        self.ok = False
        self.elapsed = 0.0
        self.output = []


def _deploy_thread(state, cmd, cwd, extra_env):
    merged = {**os.environ, **(extra_env or {})}
    start = time.monotonic()
    state.phase = "starting..."
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=cwd, env=merged, bufsize=1,
        )
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            state.output.append(line)
            phase = parse_phase(line)
            if phase:
                state.phase = phase
            state.elapsed = time.monotonic() - start
        proc.wait(timeout=300)
        state.elapsed = time.monotonic() - start
        state.ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        state.elapsed = time.monotonic() - start
        state.ok = False
    except Exception:
        state.elapsed = time.monotonic() - start
        state.ok = False
    state.done = True


def _build_tasks(services, env_vars):
    cf_key = env_vars.get("CF_API_KEY", "")
    cf_email = env_vars.get("CF_EMAIL", "")
    tasks = []
    for name in services:
        svc = SERVICES[name]
        cwd = str(BUILDZERO / svc["path"])
        if svc["type"] == "vercel":
            cmd = ["vercel", "deploy", "--prod"]
            extra = None
        else:
            if not cf_key or not cf_email:
                return None, name
            cmd = ["bunx", "wrangler", "deploy"]
            extra = {"CLOUDFLARE_API_KEY": cf_key, "CLOUDFLARE_EMAIL": cf_email}
        tasks.append((name, svc, cmd, cwd, extra))
    return tasks, None


def _print_logs(states):
    """Print full CLI output for failed/problematic services."""
    for s in states:
        print(f"  {ui.dim('│')}")
        print(f"  {ui.dim('│')}  {ui.red('─')} {ui.bold(s.name)} output:")
        for raw in s.output:
            line = strip_ansi(raw).strip()
            if line:
                print(f"  {ui.dim('│')}    {line[:160]}")


def _deploy_live(states, threads):
    """Parallel deploy with live phase transitions and completions."""
    n = len(states)
    last_phase = {}
    printed_done = set()
    done_count = 0

    while True:
        time.sleep(0.3)

        for s in states:
            # Phase transition (only significant phases)
            if not s.done and s.phase in SHOW_PHASES and s.phase != last_phase.get(s.name):
                last_phase[s.name] = s.phase
                label = f"{s.name:<14}"
                t = fmt_t(s.elapsed)
                print(
                    f"  {ui.dim('│')}  {ui.dim('·')} {label}"
                    f"{ui.dim(f'{s.phase:<20}')}{ui.dim(t)}",
                    flush=True,
                )

            # Completion
            if s.done and s.name not in printed_done:
                printed_done.add(s.name)
                done_count += 1
                tag = f"[{done_count}/{n}]"
                if s.ok:
                    ui.item_ok(s.name, f"deployed {fmt_t(s.elapsed)}", tag)
                else:
                    ui.item_fail(s.name, f"failed {fmt_t(s.elapsed)}", tag)
                sys.stdout.flush()

        if not any(t.is_alive() for t in threads):
            for s in states:
                if s.done and s.name not in printed_done:
                    printed_done.add(s.name)
                    done_count += 1
                    tag = f"[{done_count}/{n}]"
                    if s.ok:
                        ui.item_ok(s.name, f"deployed {fmt_t(s.elapsed)}", tag)
                    else:
                        ui.item_fail(s.name, f"failed {fmt_t(s.elapsed)}", tag)
            sys.stdout.flush()
            break


def phase_deploy(services, env_vars, dry_run=False):
    ui.group_mid("deploy")

    tasks, missing = _build_tasks(services, env_vars)
    if tasks is None:
        ui.item_fail(missing, "no CF_API_KEY/CF_EMAIL in .env")
        return False, []

    if dry_run:
        for name, svc, cmd, _, _ in tasks:
            ui.item_ok(name, svc["type"], " ".join(cmd))
        return True, []

    # ── parallel with live progress ──
    start_all = time.monotonic()

    states = []
    threads = []
    for name, _, cmd, cwd, extra in tasks:
        s = ServiceState(name)
        states.append(s)
        t = threading.Thread(
            target=_deploy_thread, args=(s, cmd, cwd, extra), daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()

    _deploy_live(states, threads)

    total = time.monotonic() - start_all
    seq_sum = sum(s.elapsed for s in states)
    saved = seq_sum - total

    if saved > 2:
        print(f"  {ui.dim('│')}  {ui.dim(f'  {fmt_t(total)} total · {fmt_t(saved)} saved vs sequential')}")

    # warnings for successful services (e.g. TS errors that didn't block build)
    for s in states:
        if s.ok:
            ts_warns = sum(1 for l in s.output if "error TS" in strip_ansi(l))
            if ts_warns:
                ui.item_warn(s.name, f"{ts_warns} TS warnings")

    # full logs for failed services
    failed = [s for s in states if not s.ok]
    if failed:
        _print_logs(failed)
        return False, states

    return True, states


# ── Verify ────────────────────────────────────────────

def phase_verify(services, deploy_states=None):
    ui.group_end("verify")

    results = {}

    def check(name, url):
        start = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "b0-deploy/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                if name == "web":
                    ok = status == 200
                else:
                    body = json.loads(resp.read())
                    ok = body.get("status") == "ok"
                results[name] = (ok, str(status), time.monotonic() - start)
        except Exception as e:
            results[name] = (False, str(e)[:40], time.monotonic() - start)

    threads = []
    for name in services:
        url = HEALTH_URLS.get(name)
        if url:
            t = threading.Thread(target=check, args=(name, url))
            threads.append(t)
            t.start()

    for t in threads:
        t.join(timeout=15)

    all_ok = True
    failed_names = []
    for name in services:
        if name not in results:
            continue
        ok, detail, duration = results[name]
        if ok:
            ui.item_ok(name, detail, fmt_t(duration))
        else:
            ui.item_fail(name, detail, fmt_t(duration))
            failed_names.append(name)
            all_ok = False

    # show full deploy logs for services that failed verification
    if not all_ok and deploy_states:
        failed_states = [s for s in deploy_states if s.name in failed_names]
        if failed_states:
            _print_logs(failed_states)

    return all_ok


# ── Main ──────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    flags = {"--no-test", "--dry-run"}
    no_test = "--no-test" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in flags]

    if args:
        services = [s for s in args if s in SERVICES]
        unknown = [s for s in args if s not in SERVICES]
        if unknown:
            ui.fail(f"unknown: {', '.join(unknown)}")
            print(f"    available: {', '.join(DEPLOY_ORDER)}")
            sys.exit(1)
    else:
        services = DEPLOY_ORDER

    env_vars = load_env()
    ui.header("deploy")

    # Test
    if not no_test and not dry_run:
        if not phase_test():
            print()
            ui.fail("aborted — tests failed")
            print()
            sys.exit(1)
    else:
        ui.group_start("test")
        reason = "--dry-run" if dry_run else "--no-test"
        ui.item_none("skip", ui.dim(reason))

    # Deploy
    deploy_ok, deploy_states = phase_deploy(services, env_vars, dry_run)
    if not deploy_ok:
        print()
        ui.fail("aborted — deploy failed")
        print()
        sys.exit(1)

    # Verify
    if not dry_run:
        if not phase_verify(services, deploy_states):
            print()
            ui.warn("deployed but verification failed")
            print()
            sys.exit(1)
    else:
        ui.group_end("verify")
        ui.item_none("skip", ui.dim("--dry-run"))

    print()
    ui.ok("all services deployed and verified")
    print()


if __name__ == "__main__":
    main()
