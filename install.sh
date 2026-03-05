#!/bin/bash
# b0-skill installer
# Usage (as root): curl -fsSL buildzero.ai/install | sudo bash

set -e

REPO="pedrohnas0/b0-skill"
TARGET_USER="${SUDO_USER:-$(getent passwd 1000 | cut -d: -f1 || echo $USER)}"
TARGET_HOME=$(eval echo "~$TARGET_USER")
SKILL_DIR="$TARGET_HOME/dev/.claude/skills/b0-skill"
BIN_DIR="$TARGET_HOME/.local/bin"

G='\033[32m'  # green
D='\033[2m'   # dim
B='\033[1m'   # bold
R='\033[0m'   # reset

ok()   { echo -e "  ${D}├─${R} $1$(printf '%*s' $((28 - ${#1})) '')${G}✓${R}  ${D}$2${R}"; }
last() { echo -e "  ${D}└─${R} $1$(printf '%*s' $((28 - ${#1})) '')${G}✓${R}  ${D}$2${R}"; }
fail() { echo -e "  ${D}├─${R} $1$(printf '%*s' $((28 - ${#1})) '')\033[31m✗${R}  $2"; }

# Check root
if [ "$(id -u)" -ne 0 ]; then
  echo -e "  \033[31m✗${R} run as root: curl -fsSL buildzero.ai/install | sudo bash"
  exit 1
fi

echo -e "\n  ${B}b0 install${R}\n"
echo -e "  ${D}│${R}"

# System packages
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq curl git python3 > /dev/null 2>&1
ok "system packages" "curl · git · python3"

# Claude Code
if ! su - "$TARGET_USER" -c "command -v claude" &> /dev/null; then
  su - "$TARGET_USER" -c "curl -fsSL https://claude.ai/install.sh | bash" > /dev/null 2>&1
fi
CLAUDE_V=$(su - "$TARGET_USER" -c "~/.local/bin/claude --version 2>/dev/null" || echo "?")
ok "claude code" "$CLAUDE_V"

# Clone b0-skill
if [ -d "$SKILL_DIR/.git" ]; then
  su - "$TARGET_USER" -c "git -C '$SKILL_DIR' pull -q" 2>/dev/null
  ok "b0-skill" "updated"
else
  su - "$TARGET_USER" -c "mkdir -p '$(dirname "$SKILL_DIR")' && git clone -q 'https://github.com/$REPO.git' '$SKILL_DIR'"
  ok "b0-skill" "cloned"
fi

# .env
if [ ! -f "$SKILL_DIR/.env" ]; then
  cp "$SKILL_DIR/.env.example" "$SKILL_DIR/.env"
  chown "$TARGET_USER:$TARGET_USER" "$SKILL_DIR/.env"
  chmod 600 "$SKILL_DIR/.env"
  ok "env" "edit $SKILL_DIR/.env"
else
  ok "env" "exists"
fi

# Symlinks and PATH
su - "$TARGET_USER" -c "
  mkdir -p '$BIN_DIR'
  ln -sf '$SKILL_DIR/scripts/s.py' '$BIN_DIR/s'
  ln -sf '$SKILL_DIR/scripts/ghcp.py' '$BIN_DIR/ghcp'
  ln -sf '$SKILL_DIR/scripts/cf.py' '$BIN_DIR/cf'
  ln -sf '$SKILL_DIR/scripts/b0.py' '$BIN_DIR/b0'
  if ! grep -q '.local/bin' '$TARGET_HOME/.bashrc' 2>/dev/null; then
    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> '$TARGET_HOME/.bashrc'
  fi
"
last "symlinks" "s · ghcp · cf · b0"

echo -e "\n  ${G}✓${R} installed for ${B}$TARGET_USER${R}\n"
echo -e "  ${D}s <cmd>                    run with sudo${R}"
echo -e "  ${D}ghcp <repo> <path> <dest>  copy from github${R}"
echo -e "  ${D}cf <action> [args]         cloudflare api${R}"
echo -e "  ${D}b0                         environment status${R}"
echo ""
