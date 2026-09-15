#!/usr/bin/env python3
"""Regenerate the JS build's generated blocks from the files in contract/.

Two blocks, two source files: the source-quality tier rules from contract/tiers.json,
and the quick/standard/exhaustive depth budgets from contract/depths.json.

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
DEPTHS_JSON = os.path.join(ROOT, "contract", "depths.json")
JS_FILE = os.path.join(ROOT, "integrations", "claude-code", "deepresearch.js")

START = "// ── BEGIN GENERATED FROM contract/tiers.json — run tools/sync_tiers.py, do not hand-edit ──"
END = "// ── END GENERATED ─────────────────────────────────────────────────────────────────────"
D_START = "// ── BEGIN GENERATED FROM contract/depths.json — run tools/sync_tiers.py, do not hand-edit ──"
D_END = "// ── END GENERATED DEPTHS ──────────────────────────────────────────────────────────────"

# The two runtimes name these budgets differently and always have. The mapping lives
# HERE, in one place, so contract/depths.json can keep the Python engine's key names and
# neither runtime's call sites have to change.
DEPTH_KEY_JS = {"deepen": "deepenRounds", "wave_n": "wavePerRound",
                "max_verify": "maxVerify", "audit": "factAudit"}
DEPTH_ORDER = ["perspectives", "wave1", "deepen", "wave_n", "max_verify",
               "lenses", "audit", "critics", "rescue", "calibrate"]


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


def render_depths(contract: dict) -> str:
    """The JS build's depth table, emitted from contract/depths.json.

    A literal rather than a loop so the generated file stays readable in review: a
    reviewer comparing the two runtimes reads numbers, not a mapping applied at runtime.
    """
    lines = [D_START, "const DEPTH_BUDGETS = {"]
    for name, cfg in contract["depths"].items():
        fields = ", ".join(
            "%s: %s" % (DEPTH_KEY_JS.get(k, k), json.dumps(cfg[k]))
            for k in DEPTH_ORDER if k in cfg)
        lines.append("  %-12s { %s }," % (name + ":", fields))
    lines.append("}")
    lines.append(D_END)
    return "\n".join(lines)


def _replace(src: str, start: str, end: str, generated: str, what: str):
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(src):
        return None, "ERROR: generated markers not found in %s - has the %s block moved?" % (JS_FILE, what)
    return pat.sub(lambda _m: generated, src, count=1), None


def main() -> int:
    check_only = "--check" in sys.argv
    src = original = open(JS_FILE, encoding="utf-8").read()
    for source_file, start, end, renderer, what in (
            (TIERS_JSON, START, END, render, "tier"),
            (DEPTHS_JSON, D_START, D_END, render_depths, "depth"),
    ):
        contract = json.load(open(source_file, encoding="utf-8"))
        src, err = _replace(src, start, end, renderer(contract), what)
        if err:
            print(err)
            return 2
    if src == original:
        print("in sync: the JS generated blocks already match contract/tiers.json and contract/depths.json")
        return 0
    if check_only:
        print("OUT OF SYNC: integrations/claude-code/deepresearch.js does not match "
              "contract/. Run `python3 tools/sync_tiers.py` and commit the result.")
        return 1
    open(JS_FILE, "w", encoding="utf-8").write(src)
    print("synced: regenerated the tier and depth blocks in %s from contract/" % JS_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
