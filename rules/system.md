---
name: system
description: System commands, sudo, package installation and management
metadata:
  tags: sudo, apt, install, system
---

## Sudo

Use the `s` helper script for any command that needs sudo:

```bash
s <command>
```

The script is at `scripts/s.py` and symlinked to `~/.local/bin/s`.
It reads `SUDO_PASSWORD` from `.env` automatically via Python (no `source` quirk).

### Examples

```bash
s apt-get install -y git
s whoami
s systemctl restart nginx
```

## Package Installation

```bash
s apt-get update
s apt-get install -y <package>
```

## Environment

- OS: Debian 13 (trixie) on WSL2
- Shell: bash
- User: pedro
- WSL exe: `/mnt/c/Windows/System32/wsl.exe`
