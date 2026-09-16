#!/usr/bin/env sh
# Keep the hermes deployment's skill text equal to the repo's.
#
# Hermes' skill loader does not follow symlinks: neither a symlinked skill
# directory nor a symlinked SKILL.md ever registers (measured 2026-09-16: a
# telegram agent's skill_view kept serving a v1.9.2 real-file copy while both
# symlinked trees pointed at the fixed v1.12 doc on the same disk). So the
# deployment gets REAL files, and this script is the anti-drift step - run it
# after every `git pull` of the deployed repo:
#
#   cd ~/.local/share/hermes-agent/deepresearch-repo && git pull && sh contrib/hermes/sync-skill.sh
#
# Inside the hermes-agent container the same trees are visible as
# /opt/data/skills and /opt/data/profiles/glm/skills.
set -eu
HERE=$(cd "$(dirname "$0")/../.." && pwd)
SRC="$HERE/integrations/hermes/SKILL.md"
DATA="${1:-$HOME/.local/share/hermes-agent}"

[ -f "$SRC" ] || { echo "FAIL: $SRC not found - run from a deepresearch checkout"; exit 1; }

for DEST in "$DATA/skills/research/deepresearch" "$DATA/profiles/glm/skills/research/deepresearch"; do
  # A pre-existing symlink at either level never loads; replace it with a real file.
  if [ -L "$DEST" ]; then rm "$DEST"; fi
  mkdir -p "$DEST"
  if [ -L "$DEST/SKILL.md" ]; then rm "$DEST/SKILL.md"; fi
  cp "$SRC" "$DEST/SKILL.md"
  echo "installed: $DEST/SKILL.md ($(grep -m1 '^version:' "$DEST/SKILL.md" | tr -d '\r'))"
done
