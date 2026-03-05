#!/usr/bin/env python3
"""b0 — environment status and health check.

Usage: b0
"""

import subprocess
import json
import urllib.request
import sys
from pathlib import Path

SCRIPTS_DIR = Path("/home/pedro/dev/.claude/skills/b0-skill/scripts")
sys.path.insert(0, str(SCRIPTS_DIR))
import ui

SKILL_DIR = Path("/home/pedro/dev/.claude/skills/b0-skill")
ENV_FILE = SKILL_DIR / ".env"
SYMLINKS = {"s": "s.py", "ghcp": "ghcp.py", "cf": "cf.py", "b0": "b0.py"}


def run(cmd, timeout=5):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str)
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def version(cmd, flag="--version"):
    out = run([cmd, flag])
    if not out:
        return None
    # Extract version number from common formats
    for line in out.splitlines():
        for part in line.split():
            if any(c.isdigit() for c in part):
                return part.strip("()v,")
    return out.splitlines()[0]


def check_system():
    ui.group_start("system")

    # OS
    os_info = run("cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2")
    wsl = "wsl2" if Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists() else ""
    os_str = f"{os_info} {ui.dim('·')} {wsl}" if wsl else os_info
    ui.item_ok("os", os_str) if os_info else ui.item_fail("os")

    # Tools
    tools = [
        ("python", "python3", "--version"),
        ("node", "node", "--version"),
        ("git", "git", "--version"),
        ("curl", "curl", "--version"),
        ("wget", "wget", "--version"),
        ("docker", "docker", "--version"),
        ("bun", "bun", "--version"),
    ]

    for name, cmd, flag in tools:
        v = version(cmd, flag)
        if v:
            ui.item_ok(name, v)
        else:
            ui.item_none(name, ui.dim("—"))


def check_services():
    ui.group_mid("services")

    # GitHub CLI
    gh_v = version("gh", "--version")
    if gh_v:
        gh_user = run("gh api user --jq .login 2>/dev/null")
        if gh_user:
            ui.item_ok("gh", gh_v, gh_user)
        else:
            ui.item_warn("gh", gh_v, "not logged in")
    else:
        ui.item_none("gh", ui.dim("—"))

    # Cloudflare
    env = load_env()
    if env.get("CF_API_KEY") and env.get("CF_EMAIL"):
        try:
            req = urllib.request.Request("https://api.cloudflare.com/client/v4/zones")
            req.add_header("X-Auth-Email", env["CF_EMAIL"])
            req.add_header("X-Auth-Key", env["CF_API_KEY"])
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                zones = len(data.get("result", []))
                ui.item_ok("cf", f"{zones} zones", "buildzero.ai")
        except Exception:
            ui.item_warn("cf", "key configured", "connection failed")
    else:
        ui.item_none("cf", ui.dim("—"), "no credentials in .env")

    # Claude Code
    claude_v = version("claude", "--version")
    if claude_v:
        ui.item_ok("claude", claude_v)
    else:
        ui.item_none("claude", ui.dim("—"))


def check_skill():
    ui.group_mid("b0-skill")

    # Repo sync
    if (SKILL_DIR / ".git").exists():
        head = run(f"git -C {SKILL_DIR} rev-parse --short HEAD")
        status = run(f"git -C {SKILL_DIR} status --porcelain")
        if status:
            ui.item_warn("repo", "dirty", head or "?")
        else:
            ui.item_ok("repo", "clean", head or "?")
    else:
        ui.item_fail("repo", "not a git repo")

    # Env
    env = load_env()
    expected = ["SUDO_PASSWORD", "CF_API_KEY", "CF_EMAIL", "CF_ZONE_ID"]
    found = sum(1 for k in expected if env.get(k))
    if found == len(expected):
        ui.item_ok("env", f"{found}/{len(expected)} vars")
    elif found > 0:
        missing = [k for k in expected if not env.get(k)]
        ui.item_warn("env", f"{found}/{len(expected)} vars", f"missing: {', '.join(missing)}")
    else:
        ui.item_fail("env", "not configured")

    # Scripts/symlinks
    bin_dir = Path.home() / ".local" / "bin"
    all_ok = True
    scripts_status = []
    for name, target in SYMLINKS.items():
        link = bin_dir / name
        if link.exists():
            scripts_status.append(name)
        else:
            all_ok = False

    if all_ok:
        ui.item_ok("scripts", f"{ui.dim('·')} ".join(scripts_status))
    else:
        linked = [n for n in SYMLINKS if (bin_dir / n).exists()]
        missing = [n for n in SYMLINKS if not (bin_dir / n).exists()]
        ui.item_warn("scripts", f"{ui.dim('·')} ".join(linked), f"missing: {', '.join(missing)}")


def check_memory():
    ui.group_end("memory")

    memory_dir = Path.home() / "dev" / ".memory"

    if not memory_dir.exists():
        ui.item_none("status", ui.dim("—"), "not created")
        return

    if (memory_dir / ".git").exists():
        head = run(f"git -C {memory_dir} rev-parse --short HEAD")
        status = run(f"git -C {memory_dir} status --porcelain")
        remote = run(f"git -C {memory_dir} remote get-url origin")

        if status:
            ui.item_warn("repo", "dirty", head or "?")
        else:
            ui.item_ok("repo", "clean", head or "?")

        if remote:
            ui.item_ok("remote", remote.replace("https://github.com/", "").replace(".git", ""))
        else:
            ui.item_warn("remote", "none")
    else:
        ui.item_none("repo", ui.dim("—"), "not versioned")

    # Count content
    sessions = list((memory_dir / "sessions").glob("*.md")) if (memory_dir / "sessions").exists() else []
    inbox = list((memory_dir / "inbox").glob("*")) if (memory_dir / "inbox").exists() else []
    topics = [f for f in memory_dir.glob("*.md") if f.name != "README.md"]

    ui.item_ok("content", f"{len(sessions)} sessions · {len(inbox)} inbox · {len(topics)} topics")


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    ui.header("b0")
    check_system()
    check_services()
    check_skill()
    check_memory()
    print()


if __name__ == "__main__":
    main()
