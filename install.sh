#!/usr/bin/env bash
# Install deepresearch for the agent harnesses on this machine.
#
#   ./install.sh                 # detect what is present and install for it
#   ./install.sh claude-code     # Claude Code skill only
#   ./install.sh zcode           # ZCode skill only
#   ./install.sh hermes          # Hermes skill only
#   ./install.sh --uninstall     # remove what this script installed
#
# Symlinks rather than copies: edit the repo, every install sees the change.
# That is deliberate — the runtimes drifted five features apart when they
# were separate copies. The ONE exception is Hermes: its skill loader never
# follows a symlink (measured 2026-09-16), so it gets real files from
# contrib/hermes/sync-skill.sh - re-run after every pull.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-auto}"
CC_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
ZCODE_DIR="${ZCODE_SKILLS_DIR:-$HOME/.zcode/skills}"
HERMES_DIR="${HERMES_SKILLS_DIR:-$HOME/.local/share/hermes-agent/skills/research}"
# sync-skill.sh takes the hermes DATA dir (<data>/skills/research -> <data>), so only a
# path in that layout can be mapped; anything else is refused below rather than guessed.
case "$HERMES_DIR" in
  */skills/research) HERMES_DATA="$(dirname "$(dirname "$HERMES_DIR")")" ;;
  *) HERMES_DATA="" ;;
esac

say() { printf '  %s\n' "$*"; }

link() {  # link <src> <dst>
  mkdir -p "$(dirname "$2")"
  [ -e "$2" ] && [ ! -L "$2" ] && { say "SKIP $2 (exists and is not a symlink — move it first)"; return; }
  ln -sfn "$1" "$2"; say "linked $2"
}

# Removes a symlink, or a sync-skill.sh tree - a directory whose ONLY entry is SKILL.md.
# Anything else (a hand-copied skill beside its engine file, say) is left whole and named;
# never rm -rf, and never a half-removed directory.
unlink_or_tree() {
  if [ -L "$1" ]; then rm -f "$1"; say "removed $1"
  elif [ -d "$1" ]; then
    if [ "$(ls -A "$1")" = "SKILL.md" ]; then
      rm -f "$1/SKILL.md" && rmdir "$1" && say "removed $1"
    else
      say "LEFT $1 (holds files this script did not put there)"
    fi
  fi
}

if [ "$TARGET" = "--uninstall" ]; then
  unlink_or_tree "$CC_DIR/deepresearch"
  unlink_or_tree "$ZCODE_DIR/deepresearch"
  # Hermes: every tree and watchdog copy sync-skill.sh installed. `rm -f` on the
  # tree failed with "Is a directory" once sync had replaced the old symlink, and
  # the watchdog copies were never removed at all (review 2026-09-27).
  unlink_or_tree "$HERMES_DIR/deepresearch"
  if [ -n "$HERMES_DATA" ]; then
    for p in "$HERMES_DATA"/profiles/*; do
      [ -d "$p" ] || continue
      unlink_or_tree "$p/skills/research/deepresearch"
      rm -f "$p/scripts/deepresearch-watchdog.sh"
    done
    rm -f "$HERMES_DATA/scripts/deepresearch-watchdog.sh"
  fi
  say "uninstalled"; exit 0
fi

echo "deepresearch install — repo at $REPO"

if [ "$TARGET" = "auto" ] || [ "$TARGET" = "claude-code" ]; then
  if [ -d "$HOME/.claude" ] || [ "$TARGET" = "claude-code" ]; then
    link "$REPO/integrations/claude-code" "$CC_DIR/deepresearch"
  else say "no ~/.claude — skipping Claude Code"; fi
fi

if [ "$TARGET" = "auto" ] || [ "$TARGET" = "zcode" ]; then
  if [ -d "$ZCODE_DIR" ] || [ "$TARGET" = "zcode" ]; then
    # The skill runs the pipeline ON the ZCode agent itself (its subagents are the
    # panel, its WebSearch/WebFetch are the retrieval), so the repo checkout must
    # stay reachable for the deterministic checkers - the symlink guarantees that.
    link "$REPO/integrations/zcode" "$ZCODE_DIR/deepresearch"
  else say "no ~/.zcode/skills — skipping Zcode"; fi
fi

if [ "$TARGET" = "auto" ] || [ "$TARGET" = "hermes" ]; then
  if [ -d "$(dirname "$HERMES_DIR")" ] || [ "$TARGET" = "hermes" ]; then
    # Real files, not a link: a symlinked tree never registers in hermes, and the
    # watchdog's check used to call it current (review 2026-09-27).
    if [ -n "$HERMES_DATA" ]; then
      sh "$REPO/contrib/hermes/sync-skill.sh" "$HERMES_DATA"
    else
      say "SKIP hermes: HERMES_SKILLS_DIR must end in /skills/research (the hermes data layout); got $HERMES_DIR"
    fi
  else say "no hermes install — skipping"; fi
fi

echo
say "CLI: pip install -e \"$REPO\"   (no dependencies)"
say "or:  python3 -m deepresearch --selftest"
say "Set ANTHROPIC_API_KEY (Claude) or ZAI_API_KEY (GLM 5.3), or rely on an existing Claude Code login."
say "ZCode: /deepresearch needs no key — it runs on the session's own subscription."
