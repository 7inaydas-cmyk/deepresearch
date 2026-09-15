"""Every gate ships a good reference and a bad one, and proves both before a run.

A gate that cannot fail is indistinguishable from no gate, and this project has shipped
that shape more than once: parity markers that passed on a comment, `catchRate` counting
a partial as a catch, challenge markers that were unreachable for the input they were
added for. Each time the check was present, green, and proving nothing.

So every gate in `contract/conformance.json` carries both references, and this module
enforces the structural rule on them:

    a gate must have at least one `good` case and at least one `bad` case, and its bad
    references must produce at least one answer no good reference produces

The second half is the part that bites. A gate whose bad references answer exactly what
its good ones answer has not been shown to reject anything, however many cases it has.

`verify()` runs at preflight, before any API call, not only in CI - a deployed copy with
a broken gate refuses to start rather than producing a report nobody can check. It is
pure and takes milliseconds, so there is no reason to run it anywhere else.

The twin of this file is tests/claude-code/conformance.mjs, which applies the identical
rule to the JS build. Neither owns an expected value: both read them from the contract,
so a wrong answer the two builds happen to share still fails.

Related but not the same: probes.py injects a defect into a FINISHED REPORT to measure
whether a checker catches it. This measures the checkers themselves, before the run.
"""
from __future__ import annotations

import json
import os

from . import calibration as _cal
from . import search as _search
from . import tiers as _tiers

_HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = os.environ.get(
    "DR_CONFORMANCE_FILE", os.path.normpath(os.path.join(_HERE, "..", "contract", "conformance.json")))


def _adapter():
    """One entry per contract instrument, mapping the shared question to this runtime.

    Imported lazily: engine.py imports this module, so importing it at module level would
    be circular. Return conventions differ between the builds on purpose (a tuple here,
    an object there); normalising them is this layer's whole job, and the only place a
    runtime-specific shape is allowed to appear.
    """
    from . import engine as dr
    return {
        "webtext":             lambda s, cap: dr.webtext(s, cap),
        "tier_of":             lambda url: dr.tier_of(url)[0],
        "host_ambiguous":      lambda url: _tiers.host_is_ambiguous(url),
        "as_list":             lambda v: dr.as_list(v, "conformance"),
        "same_hypothesis":     lambda a, b: dr._same_hypothesis(dr._hyp_key(a), dr._hyp_key(b)),
        "hyp_mismatch":        lambda a, b: dr._hyp_mismatch(dr._hyp_key(a), dr._hyp_key(b)),
        "shape_problems":      lambda schema, obj: len(dr.shape(schema, obj, "conformance")[1]),
        "quote_span":          lambda page, quote: dr.quote_span(page, quote)["status"],
        "is_prose":            lambda text: _search.is_prose(text)[0],
        "looks_challenged":    lambda body: _search._looks_challenged(body),
        "calibration_verdict": lambda kappa, n: _cal.interpret(kappa, n=n)[0],
        "evidence_base":       lambda rows: dr._evidence_base(rows)["citableSources"],
        "is_nonanswer":        lambda text: dr.is_nonanswer(text),
    }


def _load(path=None):
    with open(path or CONTRACT, encoding="utf-8") as f:
        return json.load(f)


def _all_cases(doc):
    """Shared cases, then the Python-only ones, flattened to (instrument, case)."""
    out = [(fn, c) for fn, cases in doc["cases"].items() for c in cases]
    out += [(fn, c) for fn, blk in doc.get("python_cases", {}).items() for c in blk["cases"]]
    return out


def _expected(case):
    if "out_by_runtime" in case:
        return case["out_by_runtime"]["python"]
    return case["out"]


def check_structure(doc):
    """The structural rule. Returns a list of failures, empty when every gate is sound."""
    by_fn = {}
    for fn, case in _all_cases(doc):
        by_fn.setdefault(fn, []).append(case)
    bad = []
    for fn, kind in sorted(doc["instruments"].items()):
        cases = by_fn.get(fn, [])
        if not cases:
            bad.append("%s: declared in `instruments` but has no cases" % fn)
            continue
        if kind != "gate":
            continue
        good = [c for c in cases if c.get("ref") == "good"]
        evil = [c for c in cases if c.get("ref") == "bad"]
        if not good:
            bad.append("%s: a gate with no `good` reference - nothing shows it accepts what it should" % fn)
        if not evil:
            bad.append("%s: a gate with no `bad` reference - nothing shows it can reject at all" % fn)
        if not good or not evil:
            continue
        # The half that bites: a gate whose bad references answer exactly what its good
        # ones answer has not been shown to reject anything, however many cases it has.
        if not {repr(_expected(c)) for c in evil} - {repr(_expected(c)) for c in good}:
            bad.append("%s: every `bad` reference answers the same as a `good` one, so this "
                       "gate has never been observed to reject anything" % fn)
    for fn in sorted(by_fn):
        if fn not in doc["instruments"]:
            bad.append("%s: has cases but is not declared in `instruments`" % fn)
    return bad


def verify(path=None):
    """Run every reference against this build. Returns a list of failures; empty is pass.

    Failures read as sentences, not indices: a preflight that says "case 7 failed" makes
    the reader open the contract to learn what broke, which is how a gate stays broken.
    """
    doc = _load(path)
    failures = list(check_structure(doc))
    adapter = _adapter()
    # Several references deliberately trigger a recovery path that LOGS - as_list
    # announcing a double-encoded array is the point of that case. Those lines belong in
    # a real run, not on every invocation's preflight. This used to rebind the engine's
    # `log` from out here, which a review called Feature Envy and was right to; the engine
    # now owns a declared quiet_log() seam and this just uses it.
    from . import engine as _dr
    with _dr.quiet_log():
        failures += _run_cases(doc, adapter)
    return failures


def _run_cases(doc, adapter):
    failures = []
    unbound = sorted(set(doc["instruments"]) - set(adapter))
    if unbound:
        failures.append("the contract names instruments this build does not bind: %s"
                        % ", ".join(unbound))
    for fn, case in _all_cases(doc):
        if fn not in adapter:
            continue
        want = _expected(case)
        try:
            got = adapter[fn](*case["in"])
        except Exception as e:                       # noqa: BLE001 - a throwing gate is a failing gate
            failures.append("%s raised %s: %s" % (fn, type(e).__name__, case["why"]))
            continue
        got = list(got) if isinstance(got, tuple) else got
        if got != want:
            failures.append("%s expected %r, got %r — %s" % (fn, want, got, case["why"]))
    return failures


def counts(path=None):
    """(instruments, gates, cases) — for a preflight line that states its own coverage."""
    doc = _load(path)
    return (len(doc["instruments"]),
            sum(1 for v in doc["instruments"].values() if v == "gate"),
            len(_all_cases(doc)))
