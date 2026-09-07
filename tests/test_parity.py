"""Guard against the two runtimes drifting apart.

They have drifted three times, each time silently, and each time the fix was
hand-porting a feature nobody noticed was missing:

  - the Python build gained the <UNKNOWN> sentinel retry and honest rate-limit
    reporting; the JS build had neither for hours
  - the JS build's own test suite lived in a scratch directory, so nothing ran it
  - seven Python changes in one session landed with none of them in the JS build

They share `contract/tiers.json` and nothing else, so parity is a property nobody
observes unless something checks. This is that something.

A feature is listed here by the marker string that proves it exists in each
build. Markers are deliberately crude: the point is to notice absence, not to
verify behaviour — the two suites do that.

Genuinely runtime-specific things belong in PYTHON_ONLY with a reason. That list
is the honest part of this file: it records what the two builds do NOT share and
why, so "not at parity" never quietly becomes the normal state.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PY = ["deepresearch/engine.py", "deepresearch/search.py",
      "deepresearch/tiers.py", "deepresearch/calibration.py"]
JS = ["integrations/claude-code/deepresearch.js"]

# feature -> (python marker, js marker)
SHARED = {
    "framing/plan split":        ("S_FRAMING", "FRAMING_SCHEMA"),
    "validation adapter":        ("def as_list", "const asList"),
    "<UNKNOWN> sentinel retry":  ("_UNKNOWN_SENTINEL", "hasUnknownSentinel"),
    "empty-array schema retry":  ("_schema_shortfall", "schemaShortfall"),
    "shaped response at seam":   ("def shape(schema, obj", "const shape = (schema, obj"),
    "framing-contract intake":   ("def load_contract(", "const intakeContract = "),
    "per-field provenance":      ('contract["provenance"] = {', "CONTRACT.provenance = "),
    "critic reads provenance":   ("def _plan_flaws_check(", "const planFlawsCheck = "),
    "corrective retry prompt":   ("YOUR PREVIOUS RESPONSE WAS REJECTED", "YOUR PREVIOUS RESPONSE WAS REJECTED"),
    "deterministic tiering":     ("def tier_of", "const tierOf"),
    "resolver handling":         ("RESOLVERS", "RESOLVERS"),
    "citable enforcement":       ("citable_only", "citableOnly"),
    "tier-first ranking":        ("TIER_RANK.get", "tierRankOf"),
    "audit key (claim,url)":     ('fact_by.get((c["claim"]', "auditKey(c.claim"),
    "rescue pass":               ("RESCUE:", "RESCUE:"),
    "citation audit":            ("citationAccuracy", "citationAccuracy"),
    "survivor-only citation acc": ("citationAccuracySurvivorsOnly", "citationAccuracySurvivorsOnly"),
    "kills attributed by lens":  ("killsByLens", "killsByLens"),
    "answer-first synthesis":    ("answerFirst", "answerFirst"),
    "hypothesis adjudication":   ("hypothesisVerdicts", "hypothesisVerdicts"),
    "coverage-limit disclosure": ("Coverage limit you MUST disclose", "Coverage limit you MUST disclose"),
    "honestLimits in report":    ("honestLimits", "honestLimits"),
    "strike/flag policy":        ("UNTRACEABLE_POLICY", "UNTRACEABLE_POLICY"),
    "calibration":               ("cohenKappa", "cohenKappa"),
    "per-lens agreement":        ("per_lens_agreement", "perLens"),
    "near-degenerate guard":     ("minority < 2", "minority < 2"),
    "balanced calib. sample":    ("calibration_sample", "calibrationSample"),
    "amended gate (n + lens)":   ("MIN_LENS_KAPPA", "MIN_LENS_KAPPA"),
    "double-encoded recovery":   ("recovered a double-encoded array", "recovered a double-encoded array"),
    "verbatim strike":           ("untraceableVerbatim", "untraceableVerbatim"),
    "process critic":            ("processCritique", "processCritique"),
    "partial citations surfaced": ("citationPartials", "citationPartials"),
    "critique leads with count":  ("untraceableCount", "untraceableCount"),
}

# Deliberately not shared. Each entry must say WHY, so this list cannot become a
# dumping ground for "we forgot to port it".
PYTHON_ONLY = {
    "contract persisted beside report":
        "The Workflow runtime has no filesystem, so the JS build cannot write "
        "<out>.contract.json. Its report carries the same scopeContract with provenance, "
        "which the caller can save; the Python CLI writes it because it already writes --out.",
    "selftest DEGRADED gate":
        "The JS build has no selftest: the Claude Code Workflow runtime owns search, "
        "fetch, credentials and concurrency, so there is nothing for this build to "
        "preflight. Exit codes are meaningless inside a workflow too.",
    "credential preflight":
        "The JS build runs inside the Claude Code Workflow runtime, which owns "
        "authentication. There is no credential for this build to preflight.",
    "keyless search module":
        "The JS build uses the runtime's WebSearch/WebFetch tools. search.py exists "
        "because the CLI has no such tools to borrow.",
    "dropped-claim sampling":
        "Needs a second panel pass over discarded claims. Portable in principle; "
        "not yet ported, and tracked as a known gap rather than an oversight.",
    "injected-defect probes":
        "probes.py and its runner operate on a finished report, not on the engine, so "
        "`python3 -m deepresearch.probes --report <any report.json>` already scores a "
        "report from either build. Nothing to port.",
}


def read(paths):
    out = ""
    for rel in paths:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            out += f.read()
    return out


def check_tier_data():
    """Marker-string parity only proves `tierOf` exists in both files - it cannot see
    WHAT the rules say. Measured 2026-09-07: researchgate.net graded T4 in Python and T3
    in JS, listverse.com T5-excluded in Python and T3-citable in JS, and the marker check
    passed the whole time. tools/sync_tiers.py generates the JS block FROM
    contract/tiers.json; this just asks it whether the two still match."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import sync_tiers
    contract = __import__("json").load(open(sync_tiers.TIERS_JSON, encoding="utf-8"))
    generated = sync_tiers.render(contract)
    js = read(JS)
    return generated in js


def main():
    py, js = read(PY), read(JS)
    missing_py, missing_js = [], []
    for feature, (pm, jm) in sorted(SHARED.items()):
        if pm not in py:
            missing_py.append((feature, pm))
        if jm not in js:
            missing_js.append((feature, jm))

    for feature in sorted(SHARED):
        pm, jm = SHARED[feature]
        mark = "ok " if (pm in py and jm in js) else "GAP"
        print("  %s  %-28s python=%-4s js=%s"
              % (mark, feature, "yes" if pm in py else "NO", "yes" if jm in js else "NO"))

    print("\n  Python-only, by design:")
    for k, why in sorted(PYTHON_ONLY.items()):
        print("    - %-24s %s" % (k, why.split(". ")[0].rstrip(".") + "."))

    tiers_ok = check_tier_data()
    print("  %s  %-28s python=contract/tiers.json  js=%s"
          % ("ok " if tiers_ok else "GAP", "tier DATA (not just tierOf)",
             "generated, matches" if tiers_ok else "STALE - run tools/sync_tiers.py"))

    if missing_js or missing_py or not tiers_ok:
        print("\n  DRIFT DETECTED — a feature exists in one runtime and not the other.")
        for f, m in missing_js:
            print("    JS build is missing %r (marker %r)" % (f, m))
        for f, m in missing_py:
            print("    Python build is missing %r (marker %r)" % (f, m))
        if not tiers_ok:
            print("    JS tier rules do not match contract/tiers.json - "
                  "run `python3 tools/sync_tiers.py` and commit the result.")
        print("\n  Port it, or move it to PYTHON_ONLY with a reason. Do not delete the row.")
        return 1
    print("\n  ======== parity: %d shared features + tier data, 0 drift ========" % len(SHARED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
