#!/usr/bin/env python3
"""Regenerate the JS build's tier-rule block from contract/tiers.json.

Why this exists: contract/tiers.json's own $comment claims both runtimes read it. The
JS build could not - it runs inside the Claude Code Workflow runtime, which has no
filesystem at run time - so someone hand-copied the rules into deepresearch.js once and
the copy went stale. Measured 2026-09-07: researchgate.net graded T4 (discovery-only) in
Python and T3 (citable) in JS; listverse.com T5-excluded in Python, T3-citable in JS; no
T5 host list existed in JS at all. The parity test passed throughout, because it checked
that the name `tierOf` exists in both files, never what the rules said.

This script is the fix: one script, run before every commit that touches tiers.json,
that regenerates the JS constants byte-for-byte from the JSON. Run it, then diff.

    python3 tools/sync_tiers.py [--check]

--check exits 1 if the JS file would change, without writing - for CI.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TIERS_JSON = os.path.join(ROOT, "contract", "tiers.json")
JS_FILE = os.path.join(ROOT, "integrations", "claude-code", "deepresearch.js")

START = "// ── BEGIN GENERATED FROM contract/tiers.json — run tools/sync_tiers.py, do not hand-edit ──"
END = "// ── END GENERATED ─────────────────────────────────────────────────────────────────────"


def render(contract: dict) -> str:
    lines = [START]
    lines.append("const RESOLVERS = new Set(%s)" % json.dumps(sorted(contract["resolvers"])))
    lines.append("const TIER_RULES = [")
    for tier, pattern in contract["rules"]:
        # Emit the pattern as a JS STRING and compile with `new RegExp(..., 'i')` rather
        # than a `/pattern/i` literal. The JSON string is already correctly escaped by
        # json.dumps, so this is exact and cannot be broken by a literal `/` in a rule.
        lines.append("  ['%s', new RegExp(%s, 'i')]," % (tier, json.dumps(pattern)))
    lines.append("]")
    lines.append("const FARM_TELLS = new RegExp(%s, 'i')" % json.dumps(contract["farm_tells"]))
    lines.append("const TIER_RANK = %s" % json.dumps(contract["rank"]))
    lines.append("const CITABLE = new Set(%s)" % json.dumps(contract["citable"]))
    lines.append(END)
    return "\n".join(lines)


def main() -> int:
    check_only = "--check" in sys.argv
    contract = json.load(open(TIERS_JSON, encoding="utf-8"))
    generated = render(contract)
    src = open(JS_FILE, encoding="utf-8").read()
    pat = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pat.search(src):
        print("ERROR: generated markers not found in %s - has the tier block moved?" % JS_FILE)
        return 2
    new_src = pat.sub(lambda _m: generated, src, count=1)
    if new_src == src:
        print("in sync: JS tier rules already match contract/tiers.json")
        return 0
    if check_only:
        print("OUT OF SYNC: integrations/claude-code/deepresearch.js does not match "
              "contract/tiers.json. Run `python3 tools/sync_tiers.py` and commit the result.")
        return 1
    open(JS_FILE, "w", encoding="utf-8").write(new_src)
    print("synced: regenerated the tier block in %s from contract/tiers.json" % JS_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
