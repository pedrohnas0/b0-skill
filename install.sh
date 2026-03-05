#!/bin/bash
# b0-skill installer
# Usage (as root): curl -fsSL buildzero.ai/install | bash
# Or: sudo bash -c "$(curl -fsSL buildzero.ai/install)"

set -e

REPO="pedrohnas0/b0-skill"
TARGET_USER="${SUDO_USER:-$(getent passwd 1000 | cut -d: -f1 || echo $USER)}"
TARGET_HOME=$(eval echo "~$TARGET_USER")
SKILL_DIR="$TARGET_HOME/dev/.claude/skills/meta"
BIN_DIR="$TARGET_HOME/.local/bin"

# Check root
if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: curl -fsSL <url> | sudo bash"
  exit 1
fi

echo "=== b0-skill installer ==="
echo "User: $TARGET_USER"

# System packages
echo "[1/4] Installing system packages..."
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq curl git python3 > /dev/null 2>&1
echo "  Done"

# Claude Code
echo "[2/4] Installing Claude Code..."
if ! su - "$TARGET_USER" -c "command -v claude" &> /dev/null; then
  su - "$TARGET_USER" -c "curl -fsSL https://claude.ai/install.sh | bash"
else
  echo "  Already installed"
fi

# Clone b0-skill
echo "[3/4] Cloning b0-skill..."
if [ -d "$SKILL_DIR/.git" ]; then
  echo "  Already exists, pulling latest..."
  su - "$TARGET_USER" -c "git -C '$SKILL_DIR' pull -q"
else
  su - "$TARGET_USER" -c "mkdir -p '$(dirname "$SKILL_DIR")' && git clone -q 'https://github.com/$REPO.git' '$SKILL_DIR'"
fi

# .env with sudo password
if [ ! -f "$SKILL_DIR/.env" ]; then
  echo "  Creating .env..."
  # Try to get password from stdin if available, otherwise prompt
  if [ -t 0 ]; then
    read -sp "  Enter sudo password for $TARGET_USER: " SUDO_PASS
    echo
  else
    SUDO_PASS=""
  fi
  if [ -n "$SUDO_PASS" ]; then
    echo "SUDO_PASSWORD=$SUDO_PASS" > "$SKILL_DIR/.env"
    chown "$TARGET_USER:$TARGET_USER" "$SKILL_DIR/.env"
    chmod 600 "$SKILL_DIR/.env"
  else
    cp "$SKILL_DIR/.env.example" "$SKILL_DIR/.env"
    chown "$TARGET_USER:$TARGET_USER" "$SKILL_DIR/.env"
    chmod 600 "$SKILL_DIR/.env"
    echo "  Edit $SKILL_DIR/.env with your sudo password"
  fi
fi

# Symlinks and PATH
echo "[4/4] Creating symlinks and PATH..."
su - "$TARGET_USER" -c "
  mkdir -p '$BIN_DIR'
  ln -sf '$SKILL_DIR/scripts/s.py' '$BIN_DIR/s'
  ln -sf '$SKILL_DIR/scripts/ghcp.py' '$BIN_DIR/ghcp'
  if ! grep -q '.local/bin' '$TARGET_HOME/.bashrc' 2>/dev/null; then
    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> '$TARGET_HOME/.bashrc'
  fi
"
echo "  Done"

echo ""
echo "=== b0-skill installed! ==="
echo "  s <cmd>                    - run with sudo"
echo "  ghcp <repo> <path> <dest>  - copy from GitHub"
echo ""
echo "Run: su - $TARGET_USER"
