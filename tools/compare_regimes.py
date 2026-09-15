"""Before/after across the two regimes, from the recorded runs themselves.

Every headline number in the README was measured on a pipeline running scholarly-only
search, with a calibration sampler biased toward survivors and a strike policy that
never struck. This reads both sets and prints the comparison, so the claim "SearXNG and
the fixes changed the numbers" is a table anyone can regenerate rather than an assertion.

    python3 tools/compare_regimes.py
    python3 tools/compare_regimes.py --dropped-md   # the README's #9 table, regenerated

The README said this table "cannot drift again" because a tool regenerates it. That was
true of the regime tables and NOT of the dropped-claim one, which stayed hand-maintained
and drifted: it listed five samples when eight were archived, omitting v3-minwage-fixed
(90% vs 67%) and v3-nudge-contract (60% vs 67%), and its headline read "four of five"
where no stated rule gives four. --dropped-md emits the block, and tests/test_pipeline.py
compares it against the README so the two cannot separate again.
"""
import glob
import sys
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


# Within this many points counts as "as well as". Stated so the headline tally is
# reproducible: the previous prose count could not be derived from any rule.
SAME_WITHIN = 5

DROPPED_START = "<!-- BEGIN GENERATED: tools/compare_regimes.py --dropped-md -->"
DROPPED_END = "<!-- END GENERATED -->"


def dropped_markdown():
    """The README's issue-#9 table, built from every archived run that carries a sample."""
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "runs", "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        ds = d.get("droppedSample")
        if not isinstance(ds, dict) or ds.get("survivalRate") is None:
            continue
        rows.append((os.path.basename(f)[:-5], ds.get("sampled"),
                     ds["survivalRate"], ds.get("keptClaimSurvivalRate") or 0))
    out = [DROPPED_START,
           "", "| Run | n | Dropped claims that survived | Kept claims that survived |",
           "|---|---|---|---|"]
    same = 0
    for name, n, sv, kp in rows:
        if 100 * (sv - kp) >= -SAME_WITHIN:
            same += 1
        out.append("| %s | %s | %.0f%% | %.0f%% |" % (name, n, 100 * sv, 100 * kp))
    # The CONCLUSION is derived, not typed. It was fixed prose asserting "the ranking is
    # not selecting for verifiability", written when the samples ran one way; a later run
    # came back 33% against 100% of kept and the sentence still asserted the old reading
    # over a bare majority. A generated table with a hand-written conclusion is only half
    # generated, and the hand-written half is the one that overstates.
    frac = same / len(rows) if rows else 0
    if frac >= 0.75:
        reading = ("The ranking is not selecting for verifiability - that is the unfavourable "
                   "answer and it is the one the data gives.")
    elif frac <= 0.25:
        reading = ("The ranking is selecting for verifiability: the claims the cap discarded "
                   "really do verify worse.")
    else:
        reading = ("At %d of %d there is **no consistent signal either way** - some runs drop "
                   "claims that verify as well as the kept ones, others drop claims that verify "
                   "worse. That is weaker than this table once claimed, and it is what the "
                   "samples support." % (same, len(rows)))
    out += ["",
            "**In %d of %d samples the discarded claims verified as well as or better than the "
            "kept ones** (within %d points, or higher). %s Tracked as "
            "[#9](https://github.com/7inaydas-cmyk/deepresearch/issues/9)."
            % (same, len(rows), SAME_WITHIN, reading),
            "", DROPPED_END]
    return "\n".join(out)


def row(path):
    d = json.load(open(path, encoding="utf-8"))
    s = d.get("stats") or {}
    ca = d.get("citationAudit") or {}
    cal = d.get("calibration") or {}
    # Top level, NOT under stats — read the wrong key once and concluded the instrument
    # had not fired when it had.
    ds = d.get("droppedSample") or {}
    hp = s.get("searchHealth") or {}
    gen = ("searxng", "ddg-html", "ddg-lite", "mojeek")
    web = sum((hp.get(n) or {}).get("results", 0) for n in gen)
    ver = s.get("claimsVerified") or 0
    return {
        "run": os.path.basename(path).replace(".json", ""),
        "sources": len(d.get("sources") or []),
        "verified": ver,
        "killed": s.get("killed"),
        "killRate": round(100.0 * (s.get("killed") or 0) / ver, 1) if ver else None,
        "citeAcc": ca.get("citationAccuracy"),
        "partial": ca.get("partial"),
        "demoted": ca.get("demotedBySurvivingPanel"),
        "dropped": s.get("claimsDroppedBeforeVerify"),
        "dropSurv": ds.get("survivalRate"),
        "keptSurv": ds.get("keptClaimSurvivalRate"),
        "dropN": ds.get("sampled"),
        "kappa": cal.get("cohenKappa"),
        "calN": cal.get("n"),
        "gate": cal.get("gateVerdict"),
        "lensSplit": (cal.get("lensSplit") or {}).get("disagreementRate"),
        "genWebResults": web,
        "struck": len((d.get("processCritique") or {}).get("struckFromSummary") or []),
        "untraceable": (d.get("processCritique") or {}).get("untraceableCount",
                       len((d.get("processCritique") or {}).get("untraceableStatements") or [])),
    }


def table(rows, title):
    print("\n== %s ==" % title)
    if not rows:
        print("  (none)")
        return
    hdr = ("run", "sources", "verified", "killRate", "citeAcc", "partial", "dropped",
           "kappa", "calN", "gate", "genWeb")
    print("  %-30s %7s %8s %8s %7s %7s %7s %6s %5s %-14s %6s" % hdr)
    for r in rows:
        print("  %-30s %7s %8s %7s%% %6s%% %7s %7s %6s %5s %-14s %6s" % (
            r["run"][:30], r["sources"], r["verified"], r["killRate"], r["citeAcc"],
            r["partial"], r["dropped"], r["kappa"], r["calN"], (r["gate"] or "-")[:14],
            r["genWebResults"]))


def spread(rows, key):
    vals = sorted(v for v in (r[key] for r in rows) if isinstance(v, (int, float)))
    return "%s-%s" % (vals[0], vals[-1]) if vals else "n/a"


def main():
    if "--dropped-md" in sys.argv:
        print(dropped_markdown())
        return 0
    # A framing contract is not a run. Persisting it beside the report made
    # runs/*.json match it, and this tool listed two empty rows as if they were runs.
    paths = sorted(p for p in glob.glob(os.path.join(ROOT, "runs", "*.json"))
                   if not p.endswith(".contract.json")
                   and not os.path.basename(p).startswith("probes-"))
    new = [row(p) for p in paths if os.path.basename(p).startswith(("v2-", "v3-"))]
    old = [row(p) for p in paths if not os.path.basename(p).startswith(("v2-", "v3-"))]
    table(old, "SUPERSEDED: scholarly-only search, biased calibration sample, strike dead")
    table(new, "CURRENT: SearXNG on, all fixes in")

    print("\n== what actually moved ==")
    for label, rows in (("superseded", old), ("current", new)):
        if not rows:
            continue
        gen = [r for r in rows if r["genWebResults"] > 0]
        print("  %-11s n=%d | kill rate %s%% | citation accuracy %s%% | "
              "runs with ANY general-web result: %d of %d"
              % (label, len(rows), spread(rows, "killRate"), spread(rows, "citeAcc"),
                 len(gen), len(rows)))
    ds = [r for r in (old + new) if r["dropN"]]
    if ds:
        print("\n  dropped-claim sampling (#9) - do the discarded claims verify worse?")
        for r in ds:
            print("    %-30s n=%-3s dropped survive %s vs kept %s"
                  % (r["run"][:30], r["dropN"], r["dropSurv"], r["keptSurv"]))
    gates = [r["gate"] for r in new if r["gate"]]
    if gates:
        print("  gate verdicts, current regime: %s" % ", ".join(gates))
    print("\n  Read the kill rate as 'how much was removed', never 'removal was correct'.")
    print("  The false-kill rate is still unmeasured - see issue #12.")


if __name__ == "__main__":
    main()
