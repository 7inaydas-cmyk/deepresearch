"""Panel reliability statistics. Pure functions, no network, no model calls.

Why this module exists
----------------------
The whole tool rests on one claim: that a 2-of-3 adversarial panel is a filter
rather than a coin. That claim was asserted for the tool's entire life and never
measured. This measures it.

What it measures, and what it does NOT
--------------------------------------
Re-running the panel on the same claims measures **reliability** — does the panel
repeat itself. It does **not** measure **validity** — is the panel right. These
come apart badly for LLM judges, and it is measured, not theoretical: a 26-model
LLM panel has been recorded at Krippendorff alpha 0.77 while the human panel it
was scored against sat at 0.36, with *zero* of the 26 reproducing the minority
human reading (arXiv:2605.25652). Agreement there was a shared error mode, not
quality. Judge agreement also correlates with over-endorsement bias
(arXiv:2604.07650): "apparent agreement reflects shared error modes rather than
independent validation."

So a high kappa here licenses "proceed", never "the panel is correct". Anything
that presents this number as accuracy is misreading it.

Why two coefficients
--------------------
Cohen's kappa computes chance agreement from each rater's *own* marginals. Thakur
et al. (GEM^2 2025) declined it for exactly this reason when evaluating judges: it
"adjusts for the observed average differences between raters, which is in fact
part of what we intend to measure." Scott's pi uses the pooled marginal instead
and does not absorb that difference. Both are reported.

Both are also prevalence-sensitive. When almost every claim survives — one
recorded run killed 7% — two panels agree ~87% of the time by chance, and the
coefficient can read poorly at high accuracy. The base rate and the full
confusion matrix are therefore reported alongside, never the coefficient alone.
"""
from __future__ import annotations

__all__ = ["agreement", "per_lens_agreement", "lens_disagreement_rate", "interpret"]


def _kappa_like(a, b, pooled):
    """Chance-corrected agreement for two binary raters over the same items.

    `pooled=False` gives Cohen's kappa (per-rater marginals), `pooled=True` gives
    Scott's pi (a single pooled marginal).

    Returns (coefficient, detail). The coefficient is None when it is undefined:
    if both raters put every item in the same one category, expected agreement is
    1.0 and the correction divides by zero. That is a real and common outcome on
    a skewed base rate, and it must be reported as "undefined", never silently
    coerced to 0.0 or 1.0 — both would be a lie in opposite directions.
    """
    n = len(a)
    if n == 0:
        return None, {"n": 0, "reason": "no items"}
    yy = sum(1 for x, y in zip(a, b) if x and y)
    nn = sum(1 for x, y in zip(a, b) if not x and not y)
    yn = sum(1 for x, y in zip(a, b) if x and not y)
    ny = sum(1 for x, y in zip(a, b) if not x and y)
    po = (yy + nn) / n
    pa = (yy + yn) / n          # rater A's rate of "survives"
    pb = (yy + ny) / n          # rater B's rate of "survives"
    if pooled:
        m = (pa + pb) / 2.0
        pe = m * m + (1 - m) * (1 - m)
    else:
        pe = pa * pb + (1 - pa) * (1 - pb)
    detail = {
        "n": n, "rawAgreement": round(po, 4),
        "expectedByChance": round(pe, 4),
        "confusion": {"survive_survive": yy, "kill_kill": nn,
                      "survive_then_kill": yn, "kill_then_survive": ny},
        "surviveRateRun1": round(pa, 4), "surviveRateRun2": round(pb, 4),
    }
    # NEAR-degenerate, not just perfectly degenerate. Measured 2026-09-06: run 1
    # kept 10/10 and run 2 kept 8/10, so pe was 0.9 — under the 1.0 guard — and the
    # formula produced a confident-looking kappa of exactly 0.0, which the gate then
    # read as "the panel is noise". It is not: with no cell where both runs killed
    # the same claim, there is nothing for chance-correction to work with. A
    # coefficient computed on a marginal this lopsided is an artefact of the base
    # rate, not a measurement of the panel.
    minority = min(yy + yn, ny + nn, yy + ny, yn + nn)
    if pe < 1.0 and minority < 2:
        detail["reason"] = (
            "unreliable: the smallest marginal cell holds %d item(s) of %d. Chance "
            "agreement is %.2f, so the coefficient is pinned near zero by the base "
            "rate whatever the panel did. Re-run on a question that produces a more "
            "balanced kill rate before adjudicating any gate on this." % (minority, n, pe))
        detail["degenerate"] = True
        return None, detail
    if pe >= 1.0:
        detail["reason"] = ("undefined: both runs assigned every claim to the same "
                            "category, so chance agreement is 1.0 and the correction "
                            "divides by zero. Report the raw agreement and the base "
                            "rate instead — the coefficient carries no information here.")
        return None, detail
    return round((po - pe) / (1 - pe), 4), detail


def agreement(run_a, run_b):
    """Panel-level reliability across two independent runs of the same claims.

    `run_a` / `run_b`: sequences of booleans, True = the claim survived.
    """
    if len(run_a) != len(run_b):
        raise ValueError("runs must cover the same claims: got %d vs %d"
                         % (len(run_a), len(run_b)))
    k, detail = _kappa_like(run_a, run_b, pooled=False)
    pi, _ = _kappa_like(run_a, run_b, pooled=True)
    flips = detail["confusion"]["survive_then_kill"] + detail["confusion"]["kill_then_survive"]
    out = dict(detail)
    out.update({
        "cohenKappa": k,
        "scottPi": pi,
        "verdictFlips": flips,
        "flipRate": round(flips / detail["n"], 4) if detail["n"] else None,
        "measures": "reliability (does the panel repeat), NOT validity (is the panel right)",
    })
    return out


def per_lens_agreement(lens_a, lens_b):
    """Reliability of each lens on its own.

    If one lens carries the instability, replacing that lens is far cheaper than
    redesigning the panel — and the nearest published analogue predicts a strict
    (refutation-seeking) role will dominate a consensus rather than average into
    it, so per-lens numbers are the only way to see that happening.

    `lens_a` / `lens_b`: {lens_name: [refuted_bool, ...]} for the same claims.
    """
    out = {}
    for name in sorted(set(lens_a) & set(lens_b)):
        a, b = lens_a[name], lens_b[name]
        n = min(len(a), len(b))
        k, detail = _kappa_like(a[:n], b[:n], pooled=False)
        out[name] = {"cohenKappa": k, "rawAgreement": detail["rawAgreement"],
                     "refuteRateRun1": round(sum(a[:n]) / n, 4) if n else None,
                     "refuteRateRun2": round(sum(b[:n]) / n, 4) if n else None,
                     "n": n}
    return out


def lens_disagreement_rate(verdict_sets):
    """How often the three lenses split at all, within a single run.

    A cross-family 3-judge panel has been measured at 98.9% unanimity elsewhere.
    If our lenses agree on nearly every claim, the voting rule is close to a
    no-op and any work on thresholds or ensemble size is misdirected — the
    reliability would live in extraction and retrieval instead.

    `verdict_sets`: list of lists of refuted-booleans, one inner list per claim.
    """
    total = split = 0
    for v in verdict_sets:
        v = [bool(x) for x in v if x is not None]
        if len(v) < 2:
            continue
        total += 1
        if any(v) and not all(v):
            split += 1
    return {"claims": total, "split": split,
            "disagreementRate": round(split / total, 4) if total else None,
            "unanimityRate": round((total - split) / total, 4) if total else None}


def interpret(kappa, thresholds=(0.4, 0.6)):
    """Apply the pre-registered gate. Deliberately dumb: the thresholds were fixed
    before the experiment was built and this function must not be where they get
    quietly renegotiated."""
    lo, hi = thresholds
    if kappa is None:
        return ("undefined", "Coefficient undefined or unreliable — the base rate was too skewed for "
                             "chance correction to mean anything. The gate cannot be "
                             "adjudicated on this sample; rerun on a question that "
                             "produces a less lopsided kill rate.")
    if kappa >= hi:
        return ("calibrated", "PASS (necessary, not sufficient): proceed to the doc-vs-code "
                              "work and publish the number. This says the panel repeats "
                              "itself; it does not say the panel is right.")
    if kappa >= lo:
        return ("usable but noisy", "MIDDLE BAND: publish the number, then add abstention "
                                    "(KILL / SURVIVE / UNRESOLVED) before adding judges, and "
                                    "diversify the model rather than the prompt.")
    return ("noise", "FAIL: the central claim does not hold. Stop, drop 'adversarial "
                     "verification' as the README headline, and redesign before any polish.")
