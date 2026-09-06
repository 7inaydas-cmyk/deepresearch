#!/usr/bin/env bash
# Install deepresearch for the agent harnesses on this machine.
#
#   ./install.sh                 # detect what is present and install for it
#   ./install.sh claude-code     # Claude Code skill only
#   ./install.sh hermes          # Hermes skill only
#   ./install.sh --uninstall     # remove the symlinks
#
# Symlinks rather than copies: edit the repo, every install sees the change.
# That is deliberate — the two runtimes drifted five features apart when they
# were separate copies.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-auto}"
CC_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
HERMES_DIR="${HERMES_SKILLS_DIR:-$HOME/.local/share/hermes-agent/skills/research}"

say() { printf '  %s\n' "$*"; }

link() {  # link <src> <dst>
  mkdir -p "$(dirname "$2")"
  [ -e "$2" ] && [ ! -L "$2" ] && { say "SKIP $2 (exists and is not a symlink — move it first)"; return; }
  ln -sfn "$1" "$2"; say "linked $2"
}

if [ "$TARGET" = "--uninstall" ]; then
  rm -f "$CC_DIR/deepresearch" "$HERMES_DIR/deepresearch"
  say "removed symlinks"; exit 0
fi

echo "deepresearch install — repo at $REPO"

if [ "$TARGET" = "auto" ] || [ "$TARGET" = "claude-code" ]; then
  if [ -d "$HOME/.claude" ] || [ "$TARGET" = "claude-code" ]; then
    link "$REPO/integrations/claude-code" "$CC_DIR/deepresearch"
  else say "no ~/.claude — skipping Claude Code"; fi
fi

if [ "$TARGET" = "auto" ] || [ "$TARGET" = "hermes" ]; then
  if [ -d "$(dirname "$HERMES_DIR")" ] || [ "$TARGET" = "hermes" ]; then
    link "$REPO/integrations/hermes" "$HERMES_DIR/deepresearch"
  else say "no hermes install — skipping"; fi
fi

echo
say "CLI: pip install -e \"$REPO\"   (no dependencies)"
say "or:  python3 -m deepresearch --selftest"
say "Set ANTHROPIC_API_KEY, or rely on an existing Claude Code login."
