---
name: self
description: How to update and maintain the b0-skill itself
metadata:
  tags: self, update, git, maintenance
---

## Location

- **Local**: `/home/pedro/dev/.claude/skills/meta/`
- **Remote**: https://github.com/pedrohnas0/b0-skill
- **Branch**: main

## Updating the skill

After making changes to the skill files:

```bash
cd /home/pedro/dev/.claude/skills/meta
git add -A
git commit -m "description of change"
git push
```

The install.sh URL (`buildzero.ai/install`) always points to `main` branch, so pushes are immediately live.

## Testing the installer

Create a throwaway WSL instance to test:

```bash
# From this WSL, create a new one
printf "<user>\n<password>\n<password>\n" | /mnt/c/Windows/System32/wsl.exe --install Debian --name test-wsl

# Run installer (use commit hash to bypass GitHub cache)
/mnt/c/Windows/System32/wsl.exe -d test-wsl -u root -- bash --norc --noprofile -c \
  "apt-get update -qq > /dev/null 2>&1 && apt-get install -y -qq curl > /dev/null 2>&1 && curl -fsSL 'https://raw.githubusercontent.com/pedrohnas0/b0-skill/<commit-hash>/install.sh' | bash"

# Verify
/mnt/c/Windows/System32/wsl.exe -d test-wsl -u pedro -- bash --norc --noprofile -c \
  'export PATH="$HOME/.local/bin:$PATH" && claude --version && ls ~/dev/.claude/skills/meta/'

# Cleanup
/mnt/c/Windows/System32/wsl.exe --unregister test-wsl
```

Note: use the commit hash in the URL to bypass GitHub's raw content cache.

## Adding new rules

1. Create `rules/<name>.md` with YAML frontmatter
2. Add entry to the table in `SKILL.md`
3. Commit and push

## Adding new scripts

1. Create `scripts/<name>.py` with `#!/usr/bin/env python3`
2. Import ui: `sys.path.insert(0, str(Path("/home/pedro/dev/.claude/skills/meta/scripts"))); import ui`
3. Use `ui.*` functions for all output (see `scripts/ui.py` for available functions)
4. Make executable: `chmod +x scripts/<name>.py`
5. Symlink: `ln -sf /home/pedro/dev/.claude/skills/meta/scripts/<name>.py ~/.local/bin/<name>`
6. Add entry to the scripts table in `SKILL.md`
7. Commit and push
