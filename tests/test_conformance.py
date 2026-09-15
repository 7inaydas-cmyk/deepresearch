#!/usr/bin/env python3
"""Ask the PYTHON build every reference in contract/conformance.json.

The work lives in deepresearch/instruments.py, not here, because the same check runs at
PREFLIGHT before any API call — a deployed copy with a broken gate must refuse to start,
not merely fail someone's CI later. This file is the CI face of that one implementation.

Its twin is tests/claude-code/conformance.mjs, which asks the JS build the same
questions and applies the same structural rule.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from deepresearch import instruments   # noqa: E402


def main():
    failures = instruments.verify()
    n_inst, n_gates, n_cases = instruments.counts()
    for f in failures:
        print("  FAIL  %s" % f)
    print("\n  ======== conformance (python): %d case(s), %d instrument(s), %d gate(s), "
          "%d failure(s) ========" % (n_cases, n_inst, n_gates, len(failures)))
    if failures:
        print("\n  A gate that cannot fail is indistinguishable from no gate. Fix the gate, or")
        print("  fix the reference — but do not delete the reference to make this green.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
