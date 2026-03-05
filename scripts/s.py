#!/usr/bin/env python3
"""Runs a command with sudo using the stored password."""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path("/home/pedro/dev/.claude/skills/meta/scripts")
ENV_FILE = SCRIPTS_DIR.parent / ".env"
sys.path.insert(0, str(SCRIPTS_DIR))
import ui


def get_password():
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("SUDO_PASSWORD="):
            return line.split("=", 1)[1]
    ui.fail("SUDO_PASSWORD not found in .env")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        ui.fail("usage: s <command>")
        sys.exit(1)

    result = subprocess.run(
        ["sudo", "-S"] + sys.argv[1:],
        input=get_password() + "\n",
        text=True,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
