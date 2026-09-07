"""Before/after across the two regimes, from the recorded runs themselves.

Every headline number in the README was measured on a pipeline running scholarly-only
search, with a calibration sampler biased toward survivors and a strike policy that
never struck. This reads both sets and prints the comparison, so the claim "SearXNG and
the fixes changed the numbers" is a table anyone can regenerate rather than an assertion.

    python3 tools/compare_regimes.py
"""
import glob
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


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
