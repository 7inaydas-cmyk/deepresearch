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
# With --check it becomes a deterministic gate for the watchdog and for CI-ish
# use: exit 0 when clean, nonzero on ANY drift. Drift means a version that
# exists and disagrees - the repo doc vs the engine, a tree vs the repo doc.
# An absent tree is silent, the same semantics the engine's launch warning
# uses: absence is nothing to disagree with, and install mode creates it.
#
# Inside the hermes-agent container the same trees are visible as
# /opt/data/skills and /opt/data/profiles/<name>/skills (HERMES_HOME=/opt/data).
set -eu

MODE=install
case "${1:-}" in
  --check) MODE=check; shift ;;
esac
DATA="${1:-${HERMES_HOME:-$HOME/.local/share/hermes-agent}}"

HERE=$(cd "$(dirname "$0")/../.." && pwd)
SRC="$HERE/integrations/hermes/SKILL.md"
ENG="$HERE/deepresearch/__init__.py"

[ -f "$SRC" ] || { echo "FAIL: $SRC not found - run from a deepresearch checkout"; exit 1; }
[ -f "$ENG" ] || { echo "FAIL: $ENG not found - run from a deepresearch checkout"; exit 1; }

# Every profile gets its own tree (hermes resolves skills per profile), plus
# the shared root tree. A glob that matches nothing is skipped, not an error.
trees() {
  printf '%s\n' "$DATA/skills/research/deepresearch"
  for p in "$DATA"/profiles/*/skills/research/deepresearch; do
    [ -d "$p" ] && printf '%s\n' "$p"
  done
}

# Frontmatter-bounded on purpose: the Python twin (_frontmatter_version) stops at the
# closing --- "so a version: in the body can never masquerade as the tag" - a plain sed
# over the whole file has exactly the bug that docstring names.
fm_version() {
  awk 'NR==1 { if ($0 != "---") exit; next }
       $0 == "---" { exit }
       /^version:/ { sub(/^version:[[:space:]]*/, ""); gsub(/["\r]/, ""); print; exit }' "$1" 2>/dev/null
}

if [ "$MODE" = "check" ]; then
  eng=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ENG" | head -n 1)
  doc=$(fm_version "$SRC")
  if [ -z "$eng" ] || [ -z "$doc" ]; then
    echo "DRIFT: cannot read a version (engine='$eng' doc='$doc')"
    exit 1
  fi
  status=0
  if [ "$doc" != "$eng" ]; then
    echo "DRIFT: repo doc integrations/hermes/SKILL.md is $doc, engine is $eng"
    status=1
  fi
  # while-read over a here-doc runs in THIS shell, so drifts accumulates.
  drifts=""
  while IFS= read -r DEST; do
    [ -n "$DEST" ] || continue
    [ -f "$DEST/SKILL.md" ] || continue
    v=$(fm_version "$DEST/SKILL.md")
    if [ "$v" != "$doc" ]; then
      drifts="${drifts}DRIFT: $DEST/SKILL.md is ${v:-<unreadable>}, repo doc is $doc
"
    fi
  done <<EOF
$(trees)
EOF
  if [ -n "$drifts" ]; then
    printf '%s' "$drifts"
    status=1
  fi
  if [ "$status" -eq 0 ]; then
    echo "OK: doc $doc == engine $eng; every hermes tree present is current"
  fi
  exit "$status"
fi

# while-read over a here-doc (not `for` word-splitting) keeps the loop in this
# shell and keeps tree paths intact whatever they contain.
while IFS= read -r DEST; do
  [ -n "$DEST" ] || continue
  # A pre-existing symlink at either level never loads; replace it with a real file.
  if [ -L "$DEST" ]; then rm "$DEST"; fi
  mkdir -p "$DEST"
  if [ -L "$DEST/SKILL.md" ]; then rm "$DEST/SKILL.md"; fi
  cp "$SRC" "$DEST/SKILL.md"
  echo "installed: $DEST/SKILL.md ($(grep -m1 '^version:' "$DEST/SKILL.md" | tr -d '\r'))"
done <<EOF
$(trees)
EOF

# The watchdog rides along, so the deployment has ONE update path: git pull +
# this script. The hermes cron's monitor resolves scripts under the PROFILE's
# own scripts dir first (measured 2026-09-16: the glm cron looked at
# profiles/glm/scripts/ and nothing else), so install it there per profile,
# plus the shared dir.
wdsts="$DATA/scripts"
for p in "$DATA"/profiles/*; do
  if [ -d "$p" ]; then wdsts="$wdsts
$p/scripts"; fi
done
while IFS= read -r d; do
  [ -n "$d" ] || continue
  mkdir -p "$d"
  cp "$HERE/contrib/hermes/watchdog.sh" "$d/deepresearch-watchdog.sh"
  chmod +x "$d/deepresearch-watchdog.sh"
  echo "installed: $d/deepresearch-watchdog.sh (hermes cron monitor)"
done <<EOF
$wdsts
EOF
