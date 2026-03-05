#!/usr/bin/env python3
"""Runs a command with sudo using the stored password."""

import subprocess
import sys
from pathlib import Path

ENV_FILE = Path("/home/pedro/dev/.claude/skills/meta/.env")

def get_password():
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("SUDO_PASSWORD="):
            return line.split("=", 1)[1]
    sys.exit("SUDO_PASSWORD not found in .env")

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: s <command>")

    result = subprocess.run(
        ["sudo", "-S"] + sys.argv[1:],
        input=get_password() + "\n",
        text=True,
    )
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
