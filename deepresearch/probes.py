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
           "make_critic_probes", "score_critic_probes",
           "run_audit_probes", "run_critic_probes", "run_framing_probes", "main"]


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


# ── Runner ───────────────────────────────────────────────────────────────────
# The functions above are pure and were unit-tested from the day they were
# written. That is not the same as having RUN them: issues #10 and #11 ask what
# the real auditor and the real critic do when handed a defect, and only a live
# run answers that. This is the driver.
#
# It works on a FINISHED report rather than inside the pipeline, so a probe costs
# ~10 model calls against an existing run instead of a whole new research pass,
# and so the same probe can be pointed at a report from either runtime.

def _report_summary_and_findings(rep):
    return rep.get("summary") or "", [f for f in (rep.get("findings") or []) if isinstance(f, dict)]


def run_audit_probes(rep, n=5):
    """#11: mutate claims the auditor already called `supported`, then re-ask it.

    Mutating an ALREADY-SUPPORTED claim is the sharp version of the test. The
    auditor is on record saying that exact page supports that exact statement, so a
    negation of it is one the same auditor, on the same page, must now reject. If
    it does not, the 85-100% accuracy it reports on real runs is measuring its
    agreement with the extractor rather than citation support.
    """
    from . import engine as E
    endorsed = [d for d in (rep.get("citationDetail") or [])
                if isinstance(d, dict) and d.get("support") == "supported"
                and d.get("claim") and d.get("url")]
    probes = make_audit_probes([{"claim": d["claim"], "sourceUrl": d["url"]} for d in endorsed], n)
    if not probes:
        return {"n": 0, "reason": "the report has no claims the auditor marked `supported`"}

    pages = {}
    for pr in probes:
        u = pr["sourceUrl"]
        if u not in pages:
            pages[u] = E.web_fetch(u)

    def one(pr):
        text = pages.get(pr["sourceUrl"]) or ""
        got = E.agent(E.p_fact(pr["claim"], pr["sourceUrl"], text), E.S_FACT,
                      label="probe:audit:" + pr["probe"], max_tokens=1200)
        out = dict(pr)
        out["support"] = (got or {}).get("support")
        out["auditorReasoning"] = (got or {}).get("reasoning", "")[:400]
        return out

    results = [r for r in E.pmap(one, probes) if r]
    # An unreachable page cannot test the auditor — it tests the fetcher. Score
    # only the probes where the auditor actually had text in front of it, and say
    # how many were excluded rather than quietly counting them as catches.
    scorable = [r for r in results if r.get("support") != "unreachable"]
    excluded = len(results) - len(scorable)
    out = score_audit_probes(scorable)
    out["excludedUnreachable"] = excluded
    if excluded:
        out["excludedNote"] = ("%d probe(s) hit a page that would not fetch. Those measure the "
                               "fetcher, not the auditor, so they are excluded from the rate." % excluded)
    out["detail"] = [{"probe": r["probe"], "verdict": r.get("support"),
                      "original": r["original"][:200], "mutated": r["claim"][:200],
                      "url": r["sourceUrl"][:200]} for r in results]
    return out


def run_critic_probes(rep):
    """#10: does the critic's VERDICT move when three fabrications are added?

    The critic returned `material-gaps` in 5 of 5 recorded runs. Two readings:
    the pipeline always produces materially misleading output, or the verdict is
    saturated. Only an injected defect separates them.

    Both arms use the engine's own `p_critic`, so this scores the real prompt. The
    arms are identical except for the three appended sentences, which is what makes
    the comparison mean anything.
    """
    from . import engine as E
    depth = rep.get("depth") or "standard"
    n_critics = (E.TIERS.get(depth) or E.TIERS["standard"])["critics"]
    q = rep.get("question") or ""
    # Python reports key coverage by `subQuestionIndex` (an int); JS reports by
    # `subQuestion` (the text). Reading only the JS key against a Python report gave the
    # critic a checklist of EMPTY STRINGS, so the probe measured it on a paraphrase of the
    # prompt - through the data rather than the prompt text, which is what lifting
    # p_critic to module level was meant to prevent. Accept both.
    subqs = []
    for c in (rep.get("coverage") or []):
        if not isinstance(c, dict):
            continue
        if c.get("subQuestion"):
            subqs.append(str(c["subQuestion"]))
        elif c.get("subQuestionIndex") is not None:
            subqs.append("sub-question %s (%s)" % (c["subQuestionIndex"], c.get("status", "?")))
    persps = [p for p in (rep.get("perspectives") or []) if isinstance(p, dict)]
    confirmed = [{"claim": d.get("claim", "")} for d in (rep.get("citationDetail") or [])
                 if isinstance(d, dict) and d.get("claim")]
    summary, findings = _report_summary_and_findings(rep)
    if not summary or not confirmed:
        return {"reason": "report has no summary or no claim pool to trace against"}

    degraded, planted = make_critic_probes(summary, confirmed)

    def arm(spec):
        which, text = spec
        got = E.agent(E.p_critic(0, n_critics, q, subqs, persps, confirmed, text, findings,
                                 (rep.get("scopeContract") or {}).get("provenance")),
                      E.S_CRITIC, label="probe:critic:" + which, max_tokens=3000)
        return (which, got or {})

    jobs = [("clean", summary)] * n_critics + [("degraded", degraded)] * n_critics
    got = [x for x in E.pmap(arm, jobs) if x]
    order = ["sound", "minor-gaps", "material-gaps"]
    worst = lambda w: max([c.get("verdict", "sound") for k, c in got if k == w] or ["unknown"],
                          key=lambda v: order.index(v) if v in order else 0)
    flagged = sorted({s for k, c in got if k == "degraded"
                      for s in (c.get("untraceableStatements") or [])})
    out = score_critic_probes(planted, flagged, worst("clean"), worst("degraded"))
    out["criticsPerArm"] = n_critics
    out["plantedText"] = [p["text"] for p in planted]
    out["flaggedByDegradedArm"] = flagged[:12]
    out["cleanArmFlagged"] = sorted({s for k, c in got if k == "clean"
                                     for s in (c.get("untraceableStatements") or [])})[:12]
    return out


# ── Provenance rule (#the critic and ratified premises) ─────────────────────
# A structural test can only show the forbidden instruction is absent from the prompt.
# Whether the critic ACTS on it needs the critic. This is the A/B: the same report, the
# same prompt builder, run once with the real provenance and once with it faked to
# all-drafted. If the rule works, the ratified arm names the asker's own decisions as
# plan flaws LESS often than the arm that was told nothing was ratified.

# The shape of the violation, not a bag of words. A flaw that QUOTES a supplied field
# while saying the research ignored it is legitimate - that is "did it honour the
# decision", which the rule still asks for. The violation is a flaw that asks the ASKER
# to defend a decision they already made, and it has a recognisable phrasing.
_DEMAND_PHRASES = (
    "accepted rather than tested", "accepted instead of tested", "assumed rather than tested",
    "without establishing", "without sourcing", "without ever establishing",
    "never established", "never sourced", "never justified", "not justified",
    "fails to justify", "does not justify", "is unjustified", "arbitrary threshold",
    "no justification for", "without justifying",
)


def _targets_supplied(flaw, supplied_values):
    """Does this plan flaw demand the asker justify one of their OWN decisions?

    Tightened after the first live A/B scored a false positive: the earlier version
    matched any 6-letter word from the contract plus any word containing "justif", and
    fired on "five of six perspectives ... only one addresses spending justification" -
    a perfectly good perspective-set flaw. Both halves are now specific: a recognisable
    demand PHRASE, and a genuinely distinctive token (a number, year, or proper noun),
    never ordinary English.
    """
    low = flaw.lower()
    phrase = next((d for d in _DEMAND_PHRASES if d in low), None)
    if not phrase:
        return None
    for token in supplied_values:
        if token.lower() in low:
            return "%s | %s" % (token, phrase)
    return None


def _distinctive_tokens(contract):
    """Fragments only the asker's own framing would contain: numbers, years, proper nouns,
    hyphenated technical terms. NOT ordinary words - that is what produced the false
    positive on 'continued'."""
    import re
    out = set()
    prov = contract.get("provenance") or {}
    for field, origin in prov.items():
        if origin != "supplied":
            continue
        v = contract.get(field)
        text = " ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
        out.update(re.findall(r"\d+\.\d+", text))                      # 0.05, 0.20
        out.update(re.findall(r"\b(?:19|20)\d{2}\b", text))             # 2020, 2022
        out.update(re.findall(r"\b[A-Z][a-z]+-[A-Z]{2,}[A-Za-z]*\b", text))   # PET-PEESE
        out.update(re.findall(r"\b[A-Z]{3,}\b", text))                   # RoBMA-style
        # Proper nouns, but never at the start of a sentence, where capitals mean nothing.
        for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{3,})\b", text, re.M):
            out.add(m.group(1))
    return sorted(out)


def run_framing_probes(rep):
    """Does the critic actually respect a ratified framing? Real prompt, both arms."""
    from . import engine as E
    contract = rep.get("scopeContract") or {}
    prov = contract.get("provenance") or {}
    supplied = [f for f, v in prov.items() if v == "supplied"]
    if not supplied:
        return {"reason": "this report had no supplied framing fields, so there is nothing to respect"}
    tokens = _distinctive_tokens(contract)
    depth = rep.get("depth") or "standard"
    n_critics = (E.TIERS.get(depth) or E.TIERS["standard"])["critics"]
    q = rep.get("question") or ""
    subqs = []
    for c in (rep.get("coverage") or []):
        if isinstance(c, dict):
            subqs.append(str(c.get("subQuestion") or "sub-question %s (%s)"
                              % (c.get("subQuestionIndex"), c.get("status", "?"))))
    persps = [p for p in (rep.get("perspectives") or []) if isinstance(p, dict)]
    confirmed = [{"claim": d.get("claim", "")} for d in (rep.get("citationDetail") or [])
                 if isinstance(d, dict) and d.get("claim")]
    summary, findings = _report_summary_and_findings(rep)
    faked = {f: "drafted" for f in prov}

    def arm(spec):
        which, p = spec
        got = E.agent(E.p_critic(0, n_critics, q, subqs, persps, confirmed, summary, findings, p),
                      E.S_CRITIC, label="probe:framing:" + which, max_tokens=3000)
        return (which, got or {})

    jobs = [("ratified", prov)] * n_critics + [("as-if-drafted", faked)] * n_critics
    got = [x for x in E.pmap(arm, jobs) if x]
    hits = {}
    for which in ("ratified", "as-if-drafted"):
        flaws = [f for k, c in got if k == which for f in (c.get("planFlaws") or [])]
        found = [(f, _targets_supplied(f, tokens)) for f in flaws]
        hits[which] = {"planFlaws": len(flaws),
                       "demandingJustificationOfASuppliedField":
                           [{"matched": t, "flaw": f[:260]} for f, t in found if t],
                       # every flaw, so the detector can be re-scored without re-running
                       # the critic - the first version of it was wrong and re-running to
                       # find that out cost four model calls.
                       "allFlaws": [f[:400] for f in flaws]}
    a = len(hits["ratified"]["demandingJustificationOfASuppliedField"])
    b = len(hits["as-if-drafted"]["demandingJustificationOfASuppliedField"])
    return {
        "suppliedFields": supplied, "tokensWatched": tokens[:12],
        "criticsPerArm": n_critics, "arms": hits,
        "reading": (
            "the rule holds: the ratified arm demanded nothing and the as-if-drafted arm "
            "demanded %d" % b if a == 0 and b >= 2 else
            "the rule is NOT working: the ratified arm demands the asker justify a decision "
            "they made, and the as-if-drafted arm does not" if a > 0 and b == 0 else
            "INCONCLUSIVE at this sample size. ratified=%d as-if-drafted=%d, with %d critic(s) "
            "per arm and a keyword detector over free text. Two runs of this probe on the same "
            "report gave (1, 6) and (1, 0) - the run-to-run variance is larger than the effect, "
            "and BOTH ratified hits were false positives on inspection ('spending justification' "
            "as a topic, and 'Large' from the asker's own quoted phrase). Read allFlaws yourself; "
            "do not quote a verdict from this number." % (a, b, n_critics)),
        "measures": "whether the critic ACTS on provenance, not whether it was told about it",
        "instrumentLimits": (
            "A keyword detector over free-text plan flaws is a weak instrument and this one has "
            "produced a false positive on every run so far. The STRUCTURAL claim - that the "
            "forbidden instruction is absent from the prompt when a field is ratified - is "
            "deterministic and is tested in tests/test_pipeline.py. This probe tests something "
            "harder and does not yet do it reliably. Settling it needs many more arms, or a "
            "model judge asked 'does this flaw demand the asker justify their own decision?', "
            "which is itself an unvalidated judge."),
    }


def main():
    import argparse
    import json
    import sys
    ap = argparse.ArgumentParser(
        description="Inject defects into a finished report and measure whether the citation "
                    "auditor (#11) and the process critic (#10) catch them. Manufactures the "
                    "ground truth that real output does not have.")
    ap.add_argument("--report", "-r", required=True, help="a finished report JSON")
    ap.add_argument("--out", "-o", help="write the probe result here")
    ap.add_argument("--audit-n", type=int, default=5, help="how many citation probes to inject")
    ap.add_argument("--only", choices=["audit", "critic", "framing"],
                    help="run just one of the three")
    a = ap.parse_args()

    from . import engine as E
    E.preflight()
    rep = json.load(open(a.report, encoding="utf-8"))
    res = {"report": a.report, "question": (rep.get("question") or "")[:200],
           "measures": "detection of INJECTED defects, not validity of the pipeline as a whole"}
    if a.only not in ("critic", "framing"):
        E.log("Injecting %d citation-audit probes (#11)..." % a.audit_n)
        res["auditProbes"] = run_audit_probes(rep, a.audit_n)
        E.log("  catch rate: %s" % res["auditProbes"].get("catchRate"))
    if a.only == "framing" or a.only is None:
        E.log("Re-running the critic with the real provenance and with it faked to all-drafted...")
        res["framingProbes"] = run_framing_probes(rep)
        E.log("  " + str(res["framingProbes"].get("reading") or res["framingProbes"].get("reason")))
    if a.only not in ("audit", "framing"):
        E.log("Running the process critic on a clean and a degraded summary (#10)...")
        res["criticProbes"] = run_critic_probes(rep)
        E.log("  clean=%s degraded=%s moved=%s"
              % (res["criticProbes"].get("cleanVerdict"), res["criticProbes"].get("degradedVerdict"),
                 res["criticProbes"].get("verdictMoved")))
    txt = json.dumps(res, indent=1, ensure_ascii=False)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)
        print("wrote " + a.out)
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
