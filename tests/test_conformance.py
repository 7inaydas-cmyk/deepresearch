#!/usr/bin/env python3
"""Run contract/conformance.json against the PYTHON engine.

The twin of tests/claude-code/conformance.mjs, which asks the JS build the identical
questions. Neither runner owns an expected value: both read them from the contract, so
"the two runtimes agree" is checked by comparing each against one written-down answer
rather than against each other, and a wrong answer both builds share still fails.

Why this exists alongside tests/test_parity.py: that file proves a marker STRING is
present in each build. It catches a feature nobody ported; it cannot catch one ported
wrongly, and it once passed a row whose JS marker was a comment describing the
mechanism. Every drift recorded in runs/README.md was in logic of this shape.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from deepresearch import engine as dr      # noqa: E402
from deepresearch import tiers             # noqa: E402

CONTRACT = os.path.join(ROOT, "contract", "conformance.json")

# The adapter: one entry per contract function, mapping the shared question to this
# runtime's call. Return conventions differ between the builds on purpose (a tuple here,
# an object there); normalising them is this layer's whole job, and it is the only place
# a runtime-specific shape is allowed to appear.
ADAPTER = {
    "webtext":         lambda s, cap: dr.webtext(s, cap),
    "tier_of":         lambda url: dr.tier_of(url)[0],
    "host_ambiguous":  lambda url: tiers.host_is_ambiguous(url),
    "as_list":         lambda v: dr.as_list(v, "conformance"),
    "same_hypothesis": lambda a, b: dr._same_hypothesis(dr._hyp_key(a), dr._hyp_key(b)),
    "hyp_unrelated":   lambda a, b: dr._hyp_unrelated(dr._hyp_key(a), dr._hyp_key(b)),
    "shape_problems":  lambda schema, obj: len(dr.shape(schema, obj, "conformance")[1]),
}


def main():
    cases = json.load(open(CONTRACT, encoding="utf-8"))["cases"]
    missing = sorted(set(cases) - set(ADAPTER))
    if missing:
        print("  GAP  contract names functions this runtime does not bind: %s" % ", ".join(missing))
        return 1
    unused = sorted(set(ADAPTER) - set(cases))
    passed = failed = 0
    for fn in sorted(cases):
        for case in cases[fn]:
            # `out_by_runtime` pins a DIFFERENT answer per build, for the cases where the
            # platform itself differs - URL parsing is the real one. Both answers are
            # pinned, so either moving is still a failure; it is not a way to excuse drift.
            if "out_by_runtime" in case:
                want = case["out_by_runtime"]["python"]
            else:
                want = case["out"]
            got = ADAPTER[fn](*case["in"])
            got = list(got) if isinstance(got, tuple) else got
            if got == want:
                passed += 1
            else:
                failed += 1
                print("  FAIL  %s(%s)" % (fn, ", ".join(repr(a)[:48] for a in case["in"])))
                print("        expected %r, got %r" % (want, got))
                print("        %s" % case["why"])
    for fn in unused:
        print("  note  %s is bound here but has no cases in the contract" % fn)
    print("\n  ======== conformance (python): %d passed, %d failed ========" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
