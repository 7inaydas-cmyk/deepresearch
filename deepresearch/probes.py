"""Injected-defect probes for the citation auditor and the process critic.

Why
---
Two of this project's checkers report numbers that nobody has validated:

- The citation auditor scores 85–100% on real runs while the literature it cites
  for motivation puts citation support at 39–77% across 14 frontier models
  (issue #11). Either this harness is dramatically better than all of them, or the
  auditor shares a failure mode with the extractor — it refetches the same URL and
  asks the same model family a differently-worded question, so it is blind to the
  *quote*, not to the *source*. Supporting signal: `demotedBySurvivingPanel` is 0
  in every recorded run. The mechanism has never once fired in the wild.

- The process critic returns `material-gaps` in 5 of 5 runs (issue #10). A verdict
  with zero observed variance cannot separate a good run from a bad one, yet the
  skill instructs the reader to lead with it.

Neither can be settled by looking at real output, because on real output there is
no ground truth. The way through is to *manufacture* ground truth: inject a defect
you know is there and measure whether the checker finds it.

What a result means
-------------------
A high catch rate is evidence the checker works on defects of that KIND. It is not
evidence it catches subtler ones, and it is still not a validity measurement of the
pipeline as a whole. A low catch rate is the stronger signal: it means the number
the checker reports on real runs is measuring agreement-with-itself.
"""
from __future__ import annotations

__all__ = ["make_audit_probes", "score_audit_probes",
           "make_critic_probes", "score_critic_probes"]


# ── Citation auditor (#11) ───────────────────────────────────────────────────
# Each probe pairs a real source with a claim the page provably does NOT support.
# The auditor should return "unsupported" for every one. Anything it marks
# "supported" is a false negative, and a false negative here is a citation the
# tool would have published.
_AUDIT_MUTATIONS = [
    ("negated",
     "Insert a negation so the claim states the opposite of the source.",
     lambda c: "It is NOT the case that " + c[0].lower() + c[1:]),
    ("inflated-number",
     "Multiply the headline number by ten. The page states a different figure.",
     lambda c: _scale_first_number(c, 10)),
    ("unsupported-causation",
     "Convert an association into a causal claim the source does not make.",
     lambda c: c.rstrip(".") + ", and this relationship is causal rather than correlational."),
    ("fabricated-specificity",
     "Attach a precise attribution the source does not contain.",
     lambda c: c.rstrip(".") + ", as established by the 2019 Lancet consensus statement."),
    ("scope-inflation",
     "Widen the population well beyond what the source studied.",
     lambda c: c.rstrip(".") + ", and this holds for all adults worldwide regardless of age or health status."),
]


def _scale_first_number(text, factor):
    import re
    m = re.search(r"\d+(?:\.\d+)?", text)
    if not m:
        return text.rstrip(".") + " — specifically 87.4% of cases."
    try:
        val = float(m.group(0)) * factor
    except ValueError:
        return text
    new = ("%d" % val) if val == int(val) else ("%.1f" % val)
    return text[:m.start()] + new + text[m.end():]


def make_audit_probes(confirmed, n=5):
    """Build claims that are provably wrong about their own cited source.

    Takes real confirmed claims so the URL, topic and vocabulary stay realistic —
    a probe that reads like a test fixture is an easier catch than a real error.
    """
    out = []
    for i, c in enumerate(confirmed[:n]):
        kind, why, mutate = _AUDIT_MUTATIONS[i % len(_AUDIT_MUTATIONS)]
        original = c.get("claim", "")
        if not original:
            continue
        out.append({
            "probe": kind, "why": why,
            "original": original,
            "claim": mutate(original),
            "sourceUrl": c.get("sourceUrl", ""),
            "expected": "unsupported",
        })
    return out


def score_audit_probes(results):
    """`results`: the probes, each with the auditor's `support` verdict attached."""
    n = len(results)
    if not n:
        return {"n": 0, "reason": "no probes were run"}
    caught = sum(1 for r in results if r.get("support") in ("unsupported", "partial"))
    strict = sum(1 for r in results if r.get("support") == "unsupported")
    missed = [{"probe": r["probe"], "verdict": r.get("support"), "claim": r["claim"][:160]}
              for r in results if r.get("support") == "supported"]
    by_kind = {}
    for r in results:
        k = r["probe"]
        b = by_kind.setdefault(k, {"n": 0, "caught": 0})
        b["n"] += 1
        b["caught"] += 1 if r.get("support") in ("unsupported", "partial") else 0
    return {
        "n": n,
        "caughtStrict": strict, "caughtAny": caught,
        "catchRate": round(caught / n, 3),
        "falseNegatives": missed,
        "byMutation": by_kind,
        "reading": ("the auditor catches defects of this kind" if caught / n >= 0.8 else
                    "the auditor MISSES defects it should catch; the accuracy it reports on "
                    "real runs is measuring agreement with the extractor, not citation support"),
        "measures": "detection of INJECTED defects, not validity of the pipeline as a whole",
    }


# ── Process critic (#10) ─────────────────────────────────────────────────────
# Feed the critic a summary containing sentences that trace to no claim in the
# pool. It should name them. If it names them and STILL returns `material-gaps`
# on a clean summary too, the verdict scale is saturated rather than informative.
_CRITIC_INSERTS = [
    ("fabricated-attribution",
     "A named institution that appears nowhere in the claim pool."),
    ("inverted-claim",
     "A sentence asserting the opposite of what a claim states."),
    ("invented-number",
     "A specific figure with no basis in any claim."),
]


def make_critic_probes(summary, confirmed):
    """Return (degraded_summary, planted) — the summary with untraceable sentences
    appended, and the list of what was planted so it can be scored."""
    planted = [
        {"kind": _CRITIC_INSERTS[0][0],
         "text": "These findings were independently confirmed by the Wellcome Trust review panel."},
        {"kind": _CRITIC_INSERTS[1][0],
         "text": "On balance the evidence points the other way, and the effect is most likely absent."},
        {"kind": _CRITIC_INSERTS[2][0],
         "text": "The pooled effect size across studies was 0.62 (95% CI 0.55-0.69)."},
    ]
    degraded = (summary or "").rstrip() + " " + " ".join(p["text"] for p in planted)
    return degraded, planted


def score_critic_probes(planted, flagged, clean_verdict, degraded_verdict):
    """Did the critic name the planted sentences, and did its VERDICT move?

    The second half is the point of issue #10. A critic that names the defects but
    returns `material-gaps` on both the clean and the degraded summary has a
    verdict scale that carries no information, however good its prose is.
    """
    joined = " ".join(flagged or []).lower()
    hits = [p for p in planted if any(w in joined for w in _keywords(p["text"]))]
    return {
        "planted": len(planted),
        "named": len(hits),
        "detectionRate": round(len(hits) / len(planted), 3) if planted else None,
        "missed": [p["kind"] for p in planted if p not in hits],
        "cleanVerdict": clean_verdict,
        "degradedVerdict": degraded_verdict,
        "verdictMoved": clean_verdict != degraded_verdict,
        "reading": ("the verdict responds to injected defects" if clean_verdict != degraded_verdict else
                    "the verdict did NOT move when three fabricated sentences were added — it is "
                    "saturated, and cannot discriminate a good run from a bad one"),
    }


def _keywords(sentence):
    stop = {"the", "and", "was", "were", "this", "that", "with", "from", "these",
            "their", "most", "other", "than", "have", "has", "for", "are", "its"}
    return [w.strip(".,()%").lower() for w in sentence.split()
            if len(w) > 4 and w.strip(".,()%").lower() not in stop][:6]
