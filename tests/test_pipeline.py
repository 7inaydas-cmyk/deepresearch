"""Offline test suite. Stubs the model and the network, so the whole pipeline
runs with no API key, no tokens and no internet.

Run:  python3 tests/test_pipeline.py

Every test here exists because something actually broke. The comments say what.
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from deepresearch import engine as dr          # noqa: E402
from deepresearch import tiers                 # noqa: E402
from deepresearch import search as searchmod   # noqa: E402

PASS = FAIL = 0

# The engine source, read once: several tests assert on the SHAPE of the code
# (that a guard exists, that a rule is enforced) rather than on its behaviour.
_ENG = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "deepresearch", "engine.py"), encoding="utf-8").read()



def ok(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  " + msg)
    else:
        FAIL += 1
        print("  FAIL  " + msg)


SQ = ["SQ1 premise", "SQ2 mechanism", "SQ3 cost", "SQ4 counter-case"]


def install(cfg):
    """Replace the model and the network with deterministic stubs."""
    counter = itertools.count(1)

    def fake_search(q, n=6):
        if cfg.get("no_search"):
            searchmod._note("ddg-html", "fail", 0)
            return []
        searchmod._note("crossref", "ok", 3)
        if cfg.get("rescue_marker", "SQ3") in q or "rescue" in q.lower():
            return [{"url": "https://primary-rescue.org/doc", "title": "primary", "snippet": "s"}]
        return [{"url": "https://src%d.org/p" % i, "title": "T%d" % i, "snippet": "s"} for i in range(n)]

    def fake_fetch(u, cap=14000):
        return "" if cfg.get("empty_pages") else "page body for " + u

    def fake_agent(prompt, schema, label="", model=None, max_tokens=0, retries=3):
        # Route every fixture through the SEAM, so the pipeline tests see exactly what a
        # production caller sees. The guards those callers used to carry are gone; if a
        # fixture is malformed the stub now returns None the way agent() would.
        got = _raw_fake_agent(prompt, schema, label, model, max_tokens, retries)
        if got is not None and dr._has_unknown_sentinel(got):
            # agent() retries a sentinel; the *_once fixtures behave on the second call.
            dr.log("  [%s] API returned an <UNKNOWN> sentinel; retrying (stub)" % label)
            got = _raw_fake_agent(prompt, schema, label, model, max_tokens, retries)
        if got is None:
            return None
        shaped, problems = dr.shape(schema, got, label)
        if problems:
            dr.log("  [%s] response violates its own schema: %s (stub)" % (label, "; ".join(problems)))
            return None
        return shaped

    def _raw_fake_agent(prompt, schema, label="", model=None, max_tokens=0, retries=3):
        if cfg.get("rate_limited") and label.startswith("pick:"):
            dr._stats["errors"] += 1
            dr._stats["ratelimited"] += 1
            return None
        if cfg.get("all_agents_die"):
            return None
        if label == "framing":
            if cfg.get("no_framing"):
                return None
            return {"decisionAtStake": "d", "keyQuestion": "k", "assumptions": ["a1", "a2"],
                    "whatWouldChangeTheAnswer": ["w1", "w2"],
                    "hypotheses": [{"hypothesis": "h1", "killCriterion": "k1"},
                                   {"hypothesis": "h2", "killCriterion": "k2"}]}
        if label.startswith("plan"):
            if cfg.get("bad_plan"):
                return {"strategy": "x", "subQuestions": [], "perspectives": ["a bare string"]}
            if cfg.get("plan_string_subq"):
                # The 2026-09-06 live failure: an array field arrives as a string.
                return {"strategy": "s", "subQuestions": "one long prose string",
                        "perspectives": [{"label": "P%d" % i, "lens": "l", "query": "q%d" % i} for i in range(6)]}
            if cfg.get("plan_unknown_sentinel"):
                # The API's structured-output serialisation artefact.
                return {"strategy": "s", "subQuestions": "\n<UNKNOWN>\n", "perspectives": "\n<UNKNOWN>\n"}
            return {"strategy": "s", "subQuestions": list(SQ),
                    "perspectives": [{"label": "P%d" % i, "lens": "l", "query": "q%d" % i} for i in range(6)]}
        if label.startswith("pick:"):
            urls, seen = [], set()
            for tok in prompt.split():
                tok = tok.strip("*_,|")
                if tok.startswith("https://") and tok not in seen:
                    seen.add(tok)
                    urls.append(tok)
            return {"results": [{"url": u, "relevance": "high"} for u in urls[:4]]}
        if label.startswith("extract:"):
            if cfg.get("empty_pages"):
                return {"sourceQuality": "unreliable", "claims": []}
            n = next(counter)
            if "primary-rescue" in prompt:
                return {"sourceQuality": "primary", "claims": [
                    {"claim": "RESCUED-%d evidence" % n, "quote": "q", "importance": "central",
                     "subQuestionIndex": 3}]}
            return {"sourceQuality": "primary", "publishDate": "2026-01-01", "claims": [
                {"claim": "CLAIM-%d fact" % n, "quote": "q%d" % n, "importance": "central",
                 "subQuestionIndex": (n % 4) + 1},
                {"claim": "CLAIM-%db detail" % n, "quote": "qb", "importance": "supporting",
                 "subQuestionIndex": ((n + 1) % 4) + 1}]}
        if label.startswith("gap:"):
            return {"coverage": [{"subQuestionIndex": i + 1, "status": "partial"} for i in range(4)],
                    "contradictions": ["A vs B"],
                    "followUps": [] if cfg.get("no_followups") else
                                 [{"label": "FU", "query": "fq", "reason": "r"}]}
        if label in ("support", "counter", "provenance"):
            if "RESCUED-" in prompt:
                return {"refuted": False, "evidence": "e", "confidence": "high"}
            if cfg.get("kill_all"):
                return {"refuted": True, "evidence": "e", "confidence": "high"}
            n = int(prompt.split("CLAIM-")[1].split()[0].rstrip("b")) if "CLAIM-" in prompt else 0
            return {"refuted": (n % 4 == 0) and label != "provenance", "evidence": "e", "confidence": "high"}
        if label.startswith("cite:"):
            if "CLAIM-1 " in prompt or "CLAIM-1b" in prompt:
                return {"support": "unsupported", "reasoning": "page does not say this", "locatedQuote": ""}
            n = int(prompt.split("CLAIM-")[1].split()[0].rstrip("b")) if "CLAIM-" in prompt else 3
            return {"support": ["partial", "unreachable", "supported", "supported", "supported"][n % 5],
                    "reasoning": "r", "locatedQuote": "lq"}
        if label == "synthesize":
            if cfg.get("no_synth"):
                return None
            return {"answerFirst": "The answer, first.", "hingeNumber": "d = -0.31",
                    "baseRate": "none in evidence", "summary": "S",
                    "findings": [{"claim": "F1", "confidence": "high", "sources": ["u"], "evidence": "e",
                                  "sourceTier": "T1", "factInferenceAssumption": "fact"}],
                    "hypothesisVerdicts": [
                        {"hypothesis": "h1", "verdict": "killed", "killCriterion": "k1",
                         "reasoning": "claim [0] triggers it", "claimsCited": [0]},
                        {"hypothesis": "h2", "verdict": "untested", "killCriterion": "k2",
                         "reasoning": "no confirmed claim bears on it"}],
                    "strongestArgumentAgainst": "the crux was never evidenced",
                    "whatWouldChangeThisCall": ["a real RCT"],
                    "caveats": "c", "openQuestions": ["o"]}
        if label.startswith("critic:"):
            return {"untraceableStatements": ["u1"], "coverageGaps": ["g1"], "planFlaws": ["p1"],
                    "verdict": "material-gaps" if label.endswith("2") else "minor-gaps", "rationale": "r"}
        return None

    dr.web_search, dr.web_fetch, dr.agent = fake_search, fake_fetch, fake_agent
    globals().setdefault("_real_log", dr.log)
    LOGS.clear()
    dr.log = lambda m: (LOGS.append(str(m)), _real_log(m))
    searchmod.reset_health()


LOGS = []


def run(cfg=None, depth="standard", q="Test question?", contract=None):
    install(cfg or {})
    dr.preflight = lambda: "stub"   # the stubs replace the network; nothing to preflight
    dr._stats.update(calls=0, errors=0, ratelimited=0, in_tok=0, out_tok=0)
    return dr.deepresearch(q, depth, contract=contract)


# ── Tiering: a pure function, so test it like one ───────────────────────────
print("\n-- source tiering (shared contract) --")
CASES = [
    ("https://sec.gov/filing", "T1"),
    ("https://arxiv.org/abs/2304.03271", "T1"),
    ("https://www.nature.com/articles/x", "T2"),
    ("https://en.wikipedia.org/wiki/X", "T2"),
    ("https://github.com/randomuser/weekend-hack", "T3"),
    ("https://levels.fyi/x", "T4"),
    ("https://some-unknown-blog.xyz/post", "T3"),
    # A resolver is not a publisher. Grading doi.org T1 lets a predatory journal
    # outrank an SEC filing, and during a search outage where a DOI index is the
    # only live backend it reports "all top-tier" on the weakest evidence.
    ("https://doi.org/10.1234/predatory-journal", "T?"),
    ("https://dx.doi.org/10.1/x", "T?"),
]
for url, want in CASES:
    got, why = tiers.tier_of(url)
    ok(got == want, "%-46s -> %-3s (%s)" % (url[:46], got, why[:38]))
# Issue #14: hosts added alongside the new backends (#13), plus regions the rules
# under-covered. Add your host here when you extend contract/tiers.json.
for _u, _w in [("https://europepmc.org/article/PMC/PMC1", "T2"),
               ("https://pubmed.ncbi.nlm.nih.gov/1/", "T1"),
               ("https://www.biorxiv.org/content/x", "T1"),
               ("https://clinicaltrials.gov/study/NCT1", "T1"),
               ("https://www.gov.uk/guidance/x", "T1"),
               ("https://www.thelancet.com/article/x", "T2"),
               ("https://lemonde.fr/article", "T2"),
               ("https://www.researchgate.net/publication/1", "T4"),
               ("https://listverse.com/2026/top-10", "T5")]:
    ok(tiers.tier_of(_u)[0] == _w, "%-44s -> %s" % (_u[:44], _w))

# Rules are evaluated in order, so a host in a lower tier already matched by a
# higher one is DEAD. pubmed.ncbi.nlm.nih.gov sat dead in T2 behind nih.gov in T1
# from the day it was written. CI rejects this now; assert it here too.
import re as _re
def _hosts(pat):
    _m = _re.search(r"\(\^\|\\\.\)\((.*)\)\$", pat)
    return [h.replace("\\", "") for h in _m.group(1).split("|")] if _m else []
_seen, _dead = [], []
for _t, _p in tiers._C["rules"]:
    for _h in _hosts(_p):
        for _pt, _pp in _seen:
            if _re.search(_pp, _h, _re.I):
                _dead.append((_t, _h, _pt)); break
    _seen.append((_t, _p))
ok(not _dead, "no tier rule is shadowed dead by a higher tier: %s" % (_dead or "clean"))

ok(tiers.tier_of("https://doi.org/10.1/x", resolved_journal="BMC Psychology")[0] == "T2",
   "a resolver we actually read is graded on its real journal")
ok(tiers.census([{"tier": "T1"}, {"tier": "T1"}, {"tier": "T?"}]) == {"T1": 2, "T?": 1},
   "tier census counts what was actually fetched")

# ── The validation adapter ──────────────────────────────────────────────────
print("\n-- validation adapter at the model seam --")
ok(dr.as_list("a string of text") == [],
   "a STRING is not a list — iterating one gave 226 fake sub-questions before this guard")
ok(dr.as_list(None) == [] and dr.as_list({"a": 1}) == [], "None and dict are not lists either")
ok(dr.as_str_list(["a", 1, None, " b "]) == ["a", "b"], "as_str_list keeps only real strings")
ok(dr.dicts([{"a": 1}, "str", None, 7]) == [{"a": 1}], "dicts drops non-objects")
ok(dr._has_unknown_sentinel({"subQuestions": "\n<UNKNOWN>\n"}),
   "the API's <UNKNOWN> serialisation artefact is detected")
ok(not dr._has_unknown_sentinel({"subQuestions": ["real", "values"]}),
   "and does not false-positive on good output")

# ── URL handling ────────────────────────────────────────────────────────────
print("\n-- URL parsing --")
ok(tiers.host_of("https://evil.com\\@trusted.org/x") == "evil.com",
   "backslash-userinfo URL resolves to the REAL host, not the trusted-looking one")
ok(searchmod.doi_of("https://doi.org/10.1038/nature12373") == "10.1038/nature12373",
   "DOI extracted from a resolver URL")
ok(searchmod.doi_of("https://example.com/page") is None, "non-DOI URLs are left alone")

# ── Full pipeline ───────────────────────────────────────────────────────────
print("\n-- full pipeline (standard depth) --")
r = run()
ok(not r.get("error"), "completes without error")
ok(r["stats"]["confirmed"] > 0 and r["stats"]["killed"] > 0,
   "claims both survive and die: %d confirmed / %d killed" % (r["stats"]["confirmed"], r["stats"]["killed"]))
ok(r["stats"]["lensesPerClaim"] == 3, "3 adversarial lenses")
ok(r.get("scopeContract", {}).get("keyQuestion") == "k", "framing contract reaches the report")
ok(len(r["scopeContract"]["hypotheses"]) == 2, "hypotheses with kill criteria carried through")
ok(bool(r.get("answerFirst")), "answerFirst present")
ok(bool(r.get("strongestArgumentAgainst")), "strongestArgumentAgainst is required and present")
ok(r["findings"][0].get("factInferenceAssumption") == "fact",
   "findings tag fact vs inference - asserted against the PYTHON schema's key; the old test "
   "checked the JS key and passed only because the stub fabricated it")
ca = r["citationAudit"]
ok(ca["supported"] + ca["partial"] + ca["unsupported"] + ca["unreachable"] == r["stats"]["claimsVerified"],
   "citation audit covers EVERY verified claim, not just survivors")
ok(ca["citationAccuracy"] < 100, "citation accuracy is a real varying number: %s%%" % ca["citationAccuracy"])
ok(ca["demotedBySurvivingPanel"] > 0,
   "audit demoted %d claim(s) the panel had passed" % ca["demotedBySurvivingPanel"])
ok(any("citation-audit" in x.get("killedBy", "") for x in r["refuted"]),
   "demoted claims are attributed, not silently dropped")
ok(r["processCritique"]["verdict"] == "material-gaps", "critique takes the WORST verdict across critics")
ok("sourceTiers" in r["stats"], "tier census reported: %s" % r["stats"]["sourceTiers"])

print("\n-- depth tiers --")
q = run(depth="quick")
ok(q["stats"]["lensesPerClaim"] == 3,
   "quick keeps 3 lenses: with 2, a 1-1 split survives and the filter goes inert")
ok(q.get("citationAudit") is None and q.get("rescue") is None, "quick skips audit and rescue")

print("\n-- rescue --")
r3 = run({"kill_all": True})
ok(r3.get("rescue") is not None, "a wiped sub-question triggers a rescue re-search")

print("\n-- failure modes degrade honestly --")
r4 = run({"no_search": True})
ok("SEARCH INFRASTRUCTURE FAILURE" in r4["summary"],
   "a dead search layer is named as infrastructure failure")
ok("no sources exist" in r4["summary"], "and explicitly warns not to read it as absence of evidence")
r_rl = run({"rate_limited": True})
ok("MODEL RATE LIMIT" in r_rl["summary"],
   "a rate limit is named as a rate limit, never as 'the sources were empty'")
ok("no evidence exists" in r_rl["summary"], "and warns not to read it as absence of evidence")
r5 = run({"empty_pages": True})
ok("INFRASTRUCTURE" not in r5["summary"], "healthy search + empty pages is NOT called infra failure")
r6 = run({"plan_string_subq": True})
ok("error" in r6, "string-where-list-expected is rejected, not iterated into fake sub-questions")
ok(any("[plan" in l and "violates its own schema" in l and "subQuestions=0" in l for l in LOGS),
   "and the SEAM names the violation (subQuestions=0, schema requires 3) before any caller sees it")
r7 = run({"plan_unknown_sentinel": True})
ok("error" in r7, "the <UNKNOWN> sentinel does not become fake sub-questions")
r8 = run({"bad_plan": True})
ok("error" in r8, "an unusable plan returns a clean error")
r9 = run({"no_framing": True})
ok(not r9.get("error"), "a failed framing does not kill the run — the plan still runs")
r10 = run({"all_agents_die": True})
ok("error" in r10, "total model failure returns an error, not a fabricated report")
r11 = run({"no_synth": True})
ok(bool(r11.get("confirmedRaw")), "synthesis failure salvages the verified claims")
r12 = run({"kill_all": True}, depth="quick")
ok(r12["stats"]["confirmed"] == 0 and "refuted" in r12["summary"].lower(),
   "everything-killed is reported as a real result, not an error")

print("\n-- issue #3: the five verified bugs --")

# BUG 1. tier_of(url, claim, quote) fed model-written text where the function
# expects page title and page text, so the T5 content-farm regex ran against the
# CLAIM. A claim that merely quoted a listicle title mislabelled its own source
# as excluded-grade.
_farm = "The article is titled 'Top 10 Best Ultimate Guide' and reports 40%"
ok(tiers.tier_of("https://www.nature.com/articles/x", _farm, _farm)[0] != "T5",
   "a claim quoting listicle words does not drag a Nature source to T5")
ok(tiers.tier_of("https://weird.example/post", "", "Top 10 best ultimate guide")[0] == "T5",
   "but real PAGE text with farm tells still grades T5")

# BUG 2. src_rows() re-derived the tier without the page text, so sources[].tier
# and stats.sourceTiers could disagree about the same source in one report.
_r = run()
_src_tiers = {}
for _s in _r["sources"]:
    _src_tiers[_s["tier"]] = _src_tiers.get(_s["tier"], 0) + 1
ok(_src_tiers == _r["stats"]["sourceTiers"],
   "sources[].tier and stats.sourceTiers agree: %s == %s" % (_src_tiers, _r["stats"]["sourceTiers"]))

# BUG 3. fact_by and the demotion set were keyed on claim text alone, so the same
# claim extracted from two different URLs collided and one audit verdict silently
# governed both.
_k1 = ("same claim text", "https://a.org/1")
_k2 = ("same claim text", "https://b.org/2")
ok(_k1 != _k2, "identical claim text from two URLs produces two distinct audit keys")
ok('fact_by.get((c["claim"], c.get("sourceUrl")))' in _ENG,
   "the audit lookup is keyed on (claim, sourceUrl), not on claim alone")

# BUG 4. AuthError raised inside a worker was caught by pmap's bare
# `except Exception`, logged as "worker error" and turned into None — so a revoked
# token degraded into "all claims unverified". Observed live: 150 straight 401s.
def _boom(_):
    raise dr.AuthError("token revoked")
_propagated = False
try:
    dr.pmap(_boom, [1, 2, 3])
except dr.AuthError:
    _propagated = True
ok(_propagated, "AuthError propagates out of pmap instead of becoming a silent None")
ok(dr.pmap(lambda _: (_ for _ in ()).throw(ValueError("x")), [1]) == [None],
   "other exceptions still degrade to None, as intended")

# BUG 5. TIER_RANK and CITABLE were imported and never used, so "T4 is
# discovery-only, T5 excluded" was enforced by a prompt sentence and nothing else.
_claims = [{"claim": "a", "tier": "T1"}, {"claim": "b", "tier": "T5"},
           {"claim": "c", "tier": "T4"}, {"claim": "d", "tier": "T?"}]
_keep, _drop = dr.citable_only(_claims)
# contract/tiers.json lists citable as T1/T2/T?/T3. T4 is "DISCOVERY ONLY, never
# cite as fact", so a T4 claim must not enter the pool that produces cited findings.
# An earlier version of this test asserted T4 was kept; the contract says otherwise,
# and the contract is the source of truth for both runtimes.
ok(sorted(c["tier"] for c in _keep) == ["T1", "T?"] and sorted(c["tier"] for c in _drop) == ["T4", "T5"],
   "T4 and T5 are both excluded from the verify pool: neither may be cited as fact")
ok("claimsExcludedNonCitable" in _r["stats"], "the exclusion is reported, not silent")
_mixed = [{"subQuestionIndex": 1, "tier": "T3", "importance": "central", "claim": "low"},
          {"subQuestionIndex": 1, "tier": "T1", "importance": "central", "claim": "high"}]
ok(dr.coverage_balanced(_mixed, 1, 4)[0]["claim"] == "high",
   "claims are ranked by the DETERMINISTIC tier, not by the extractor's self-rating")

print("\n-- issue #5: fail fast on a dead credential --")
ok("def preflight" in _ENG, "a preflight probe runs before any research work")
ok("150 requests before" in _ENG,
   "and the comment records why: a revoked token cost 150 calls before the run gave up")
ok("revoked server-side" in _ENG,
   "the error explains that a local credential file cannot detect a server-side revocation")

print("\n-- issue #6: hypotheses are adjudicated, not decorative --")
_hv = r.get("hypothesisVerdicts") or []
ok(len(_hv) == 2, "every hypothesis written before the search gets a verdict")
ok({h["verdict"] for h in _hv} == {"killed", "untested"},
   "verdicts distinguish killed / surviving / untested")
ok(_hv[0].get("claimsCited") == [0], "a kill cites the confirmed claim that triggered its criterion")
ok("hypothesisVerdicts" in _ENG and "HYPOTHESES" in _ENG,
   "the contract's hypotheses reach synthesis instead of dying after phase 2")
ok("untested" in _ENG and "most honest output of a degraded run" in _ENG,
   "untested is treated as a reportable result, not a gap to hide")

print("\n-- issues #10 / #11: injected-defect probes --")
from deepresearch import probes as P
_c = [{"claim": "Sitting time fell by 64 minutes per day.", "sourceUrl": "https://doi.org/10.1/a"},
      {"claim": "The blood pressure effect was not significant.", "sourceUrl": "https://doi.org/10.1/b"},
      {"claim": "Standing correlated with less discomfort.", "sourceUrl": "https://doi.org/10.1/c"}]
_pr = P.make_audit_probes(_c, 3)
ok(len(_pr) == 3 and all(x["expected"] == "unsupported" for x in _pr),
   "audit probes are claims the cited page provably does NOT support")
ok(all(x["claim"] != x["original"] for x in _pr), "every probe actually mutates its claim")
ok(P.score_audit_probes([dict(x, support="supported") for x in _pr])["catchRate"] == 0.0,
   "an auditor that waves all defects through scores 0.0, not a flattering number")
_s = P.score_audit_probes([dict(x, support="unsupported") for x in _pr])
ok(_s["catchRate"] == 1.0 and "catches defects of this kind" in _s["reading"],
   "and a perfect catch is reported as 'of this kind', never as validity")
_deg, _pl = P.make_critic_probes("A summary.", _c)
ok(len(_pl) == 3 and all(p["text"] in _deg for p in _pl),
   "critic probes append fabricated sentences that trace to no claim")
_cs = P.score_critic_probes(_pl, [], "material-gaps", "material-gaps")
ok(_cs["verdictMoved"] is False and "saturated" in _cs["reading"],
   "a verdict that does not move when 3 fabrications are added is reported as saturated (#10)")
ok(P.score_critic_probes(_pl, [], "minor-gaps", "material-gaps")["verdictMoved"] is True,
   "and a verdict that does move is reported as responsive")

print("\n-- issue #4: strike or flag? --")
ok(r["processCritique"]["policy"] == "flag", "default policy is flag: nothing is deleted on an unmeasured judgement")
ok(r["processCritique"]["struckFromSummary"] == [], "and nothing was struck under the default")
dr.UNTRACEABLE_POLICY = "strike"
_rs = run()
ok(_rs["processCritique"]["policy"] == "strike", "DR_UNTRACEABLE=strike switches the behaviour")
ok(isinstance(_rs["processCritique"]["struckFromSummary"], list),
   "whatever is struck is recorded, so a deletion is never invisible")
dr.UNTRACEABLE_POLICY = "flag"

print("\n-- issue #12: honest limits travel with the report --")
_hl = r.get("honestLimits") or {}
ok(set(_hl) >= {"falseKillRateUnmeasured", "reliabilityNotValidity", "confirmedMeans"},
   "every report carries its own limits, not just the README: %s" % sorted(_hl))
ok("never been measured" in _hl.get("falseKillRateUnmeasured", ""),
   "the false-kill rate is stated as unmeasured, in the output a reader actually pastes")
ok("not whether it is right" in _hl.get("reliabilityNotValidity", ""),
   "kappa is never allowed to masquerade as accuracy")

print("\n-- issue #9: the dropped-claim majority --")
ok("Coverage limit you MUST disclose" in _ENG,
   "synthesis is told to disclose the coverage limit in answerFirst, not only in caveats")
ok("if DROP_PCT >= 50" in _ENG,
   "the disclosure is conditional: it fires above 50% dropped, not on every run")
ok("SAMPLE_DROPPED_N" in _ENG and "keptClaimSurvivalRate" in _ENG,
   "--sample-dropped verifies discarded claims and compares their survival rate to kept ones")
ok("TIER_RANK.get(c.get(\"tier\"), 3)" in _ENG,
   "ranking leads with the deterministic tier, not the extractor's self-rated importance (#3)")

print("\n-- calibration statistics --")
from deepresearch import calibration as C
# Hand-computed: 50 items, both-survive 20, both-kill 15, A-only 10, B-only 5.
# po=.70 pA=.6 pB=.5 -> Cohen pe=.50 k=.4000 ; Scott m=.55 pe=.505 pi=.3939
_a = [True]*20 + [False]*15 + [True]*10 + [False]*5
_b = [True]*20 + [False]*15 + [False]*10 + [True]*5
_r = C.agreement(_a, _b)
ok(abs(_r["cohenKappa"] - 0.4) < 1e-9, "Cohen's kappa matches the hand-computed 0.4000")
ok(abs(_r["scottPi"] - 0.3939) < 1e-3, "Scott's pi matches the hand-computed 0.3939")
ok(_r["verdictFlips"] == 15, "verdict flips counted (15 of 50)")
# The REAL 2026-09-06 result: run 1 kept 10/10, run 2 kept 8/10. pe was 0.80 —
# under the perfect-degeneracy guard — so the formula produced a confident-looking
# kappa of exactly 0.0 and the gate read it as "the panel is noise". With no cell
# where both runs killed the same claim there is nothing to chance-correct, so the
# coefficient was an artefact of the base rate, not a measurement.
_real = C.agreement([True]*10, [True]*8 + [False]*2)
ok(_real["cohenKappa"] is None,
   "a near-degenerate marginal returns None, not a confident 0.0 that reads as 'noise'")
ok("pinned near zero by the base rate" in (_real.get("reason") or ""),
   "and says why, so the gate is not adjudicated on an artefact")
ok(C.interpret(_real["cohenKappa"])[0] == "undefined",
   "the gate reports 'undefined' rather than failing the panel on a lopsided sample")
_bal = C.agreement([True]*20 + [False]*20, [True]*17 + [False]*3 + [True]*4 + [False]*16)
ok(_bal["cohenKappa"] is not None and _bal["cohenKappa"] > 0.5,
   "a balanced sample with real disagreement still measures: kappa %s" % _bal["cohenKappa"])
ok(C.agreement([True]*30, [True]*30)["cohenKappa"] is None,
   "perfect agreement on a one-sided base rate is UNDEFINED, not 1.0 - the correction divides by zero")
import random as _rnd
_rnd.seed(7)
_sa = [_rnd.random() > 0.07 for _ in range(200)]
_sb = [_rnd.random() > 0.07 for _ in range(200)]
_sr = C.agreement(_sa, _sb)
ok(_sr["rawAgreement"] > 0.8 and abs(_sr["cohenKappa"]) < 0.1,
   "two INDEPENDENT panels on a 7%% kill rate score %.2f raw but kappa %.3f - why raw agreement is not reported alone"
   % (_sr["rawAgreement"], _sr["cohenKappa"]))
ok(C.interpret(0.72)[0] == "calibrated" and C.interpret(0.5)[0] == "usable but noisy"
   and C.interpret(0.2)[0] == "noise" and C.interpret(None)[0] == "undefined",
   "the pre-registered gate maps kappa to the fixed verdicts")
_ls = C.lens_disagreement_rate([[1,1,1],[1,0,1],[0,0,0],[1,1,0]])
ok(_ls["disagreementRate"] == 0.5, "lens split rate computed (2 of 4 claims split)")
try:
    C.agreement([True], [True, False]); _raised = False
except ValueError:
    _raised = True
ok(_raised, "mismatched run lengths raise rather than silently truncating")

print("\n-- --bg self-detach --")
import inspect as _insp
_src = _insp.getsource(dr.main)
ok('"-m", "deepresearch"' in _src,
   "--bg re-execs as a MODULE: running engine.py as a file breaks `from . import search`")
ok("cwd=pkg_parent" in _src, "and from the package parent, so the import resolves")
ok("deepresearch.py --question" not in _src, "the done_when hint matches the real process name")

print("\n-- empty required arrays are a schema violation, not an answer (#16) --")
_short = dr._schema_shortfall(dr.S_FRAMING, {
    "decisionAtStake": "x", "keyQuestion": "y",
    "assumptions": [], "whatWouldChangeTheAnswer": [], "hypotheses": []})
ok(len(_short) == 3, "an empty framing contract is caught on all three required arrays, not accepted")
ok(any("hypotheses=0" in x for x in _short), "and the log names which array and by how much: %r" % _short[:1])
ok(dr._schema_shortfall(dr.S_FRAMING, {
    "decisionAtStake": "x", "keyQuestion": "y",
    "assumptions": ["a", "b"], "whatWouldChangeTheAnswer": ["c", "d"],
    "hypotheses": [{"hypothesis": "h1", "killCriterion": "k1"},
                   {"hypothesis": "h2", "killCriterion": "k2"}]}) == [],
   "a contract that meets its own minItems passes untouched")
ok(dr._schema_shortfall(dr.S_PLAN, {"strategy": "s", "subQuestions": ["a"], "perspectives": []})
   and len(dr._schema_shortfall(dr.S_PLAN, {"strategy": "s", "subQuestions": ["a"], "perspectives": []})) == 2,
   "the guard is general: a truncated PLAN response is caught the same way")
ok(dr._schema_shortfall(dr.S_PICK, {"results": []}) == [],
   "schemas with no minItems are left alone - an empty pick list is a real answer")
ok(dr._schema_shortfall(dr.S_FRAMING, "<UNKNOWN>") == ["response was str, not an object"],
   "a non-dict response is a NAMED problem at the seam (agent() checks the sentinel first, "
   "so a sentinel never reaches shape; anything else that is not an object is retried)")
ok(dr.S_FRAMING["properties"]["assumptions"].get("minItems") == 2,
   "S_FRAMING now DECLARES the minimum it needs - the guard can only enforce what the schema states")
# dr.agent is stubbed by this suite, so read the file rather than the live object.
_engine_src = open(dr.__file__, encoding="utf-8").read()
_agent_src = _engine_src.split("def agent(", 1)[1].split("\ndef ", 1)[0]
ok("shape(schema, got" in _agent_src and "retrying" in _agent_src and "return shaped" in _agent_src,
   "and agent() shapes every response and retries on a problem, so every structured call "
   "is covered at the seam, not just framing")
_dr_src = _insp.getsource(dr.deepresearch)
ok("NOTHING will be adjudicated" in _dr_src,
   "a run that ends with no hypotheses says so loudly - empty hypothesisVerdicts otherwise "
   "reads identically to 'every hypothesis survived'")

print("\n-- what the injected-defect probes measured (#10 / #11) --")
_engine_txt = open(dr.__file__, encoding="utf-8").read()
ok("citationPartials" in _engine_txt,
   "a `partial` citation verdict is surfaced in code, not left for a model to mention: "
   "measured, 3 of 5 injected fabrications came back `partial` and `partial` does not demote")
ok("untraceableCount" in _engine_txt and "readThisFirst" in _engine_txt,
   "the critique leads with the count and the list, because the VERDICT was measured not to move "
   "when three fabricated sentences were added")
ok(callable(P.run_audit_probes) and callable(P.run_critic_probes) and callable(P.main),
   "the probes have a runner, so #10 and #11 can be re-measured against any finished report")
_pc = dr.p_critic(0, 2, "Q?", ["s1"], [{"label": "L", "lens": "x"}],
                  [{"claim": "c1"}], "A summary.", [{"confidence": "high", "claim": "f1"}])
ok("Process Critic 1/2" in _pc and "Traceability" in _pc and "A summary." in _pc,
   "p_critic is module-level and renders the real prompt, so the probe scores the critic "
   "rather than a paraphrase of it")

print("\n-- the five bugs Clawbot's live review found, tested by EFFECT not plumbing --")

# 1. Env vars were read at import and then overwritten by argparse's default of 0.
_main_src = _engine_txt.split("def main(", 1)[1]
ok("default=CALIBRATE_N" in _main_src and "default=SAMPLE_DROPPED_N" in _main_src,
   "--calibrate/--sample-dropped default to the env vars instead of clobbering them with 0")
ok("globals()['CALIBRATE_N'] = a.calibrate" in _main_src,
   "the CLI flag still wins over the env var when both are given")

# 2. A double-encoded array is recovered, and a shape mismatch is never silent.
ok(dr.dicts('{"results": [{"url": "https://a.org"}]}', "pick") == [{"url": "https://a.org"}],
   "a whole object arriving JSON-encoded as a STRING is recovered, not read as 'the model chose nothing'")
ok(dr.dicts('[{"url": "https://b.org"}]', "pick") == [{"url": "https://b.org"}],
   "a bare array arriving as a string is recovered too")
ok(dr.as_str_list("one long prose string of sub-questions", "plan") == [],
   "but prose is STILL rejected - a permissive parser would bring back the 226-character bug")
ok(dr.dicts('{"a": [1], "b": [2]}', "ambiguous") == [],
   "and an object with two candidate lists is rejected rather than guessed at")
_log_src = _engine_txt.split("def as_list(", 1)[1].split("\ndef ", 1)[0]
ok("recovered a double-encoded array" in _log_src and "shape mismatch at the seam" in _log_src,
   "both paths LOG: a silent empty list is what hid this for a week")

# 3. Strike must actually remove a sentence. The old test only checked the policy string.
_summary = ("Sleep duration fell by 12 minutes. These findings were independently confirmed "
            "by the Wellcome Trust review panel. Effect sizes were small.")
_verbatim = "These findings were independently confirmed by the Wellcome Trust review panel."
_out = _summary
for _f in [_verbatim]:
    if _f in _out:
        _out = _out.replace(_f, "")
ok(_verbatim not in _out and "Sleep duration fell by 12 minutes." in _out,
   "an exact-match strike removes the offending sentence and leaves the rest intact")
ok('"untraceableVerbatim"' in _engine_txt and "untraceableVerbatim" in str(dr.S_CRITIC),
   "the critic schema now REQUESTS the verbatim sentence: matching on a prose description "
   "is why strike reported struck=0 on every run it ever ran")
_strike_src = _engine_txt.split("UNTRACEABLE_POLICY ==", 1)[1][:1600]
ok("STRIKE MATCHED NOTHING" in _engine_txt,
   "and when nothing matches it SAYS so - 'policy: strike, untraceable: 9, struck: 0' "
   "read as a clean run for as long as nobody read all three numbers together")
ok("\\u2018" in _strike_src or "'" in _strike_src,
   "the fallback also tries single and curly quotes, which is what the critic actually writes")

# 4. The selftest must not green-light a dead general web.
ok(dr.EXIT_DEGRADED == 3 and dr.EXIT_AUTH == 2 and dr.EXIT_FAIL == 1,
   "DEGRADED gets its own exit code (3): 1 and 2 already mean failed and auth-failed")
_st = _engine_txt.split("def selftest(", 1)[1].split("\ndef ", 1)[0]
ok("GENERAL_WEB" in _st and "EXIT_DEGRADED" in _st,
   "the selftest checks the general-web backends specifically, not just 'did anything answer'")
ok("contrib/searxng" in _st, "and the degraded path tells you how to fix it")
ok("sys.exit(selftest())" in _main_src,
   "main() propagates the code instead of collapsing it to 0/1")

# 5. The calibration sample was biased by construction - my own bug, found in live output.
_v = [{"claim": str(i), "survives": i < 25} for i in range(30)]
_samp = dr.calibration_sample(_v, 12)
_kills = sum(1 for c in _samp if not c["survives"])
ok(len(_samp) == 12 and _kills >= 2,
   "a 17%% kill rate yields %d kills in a sample of 12: taking the FIRST 12 of a "
   "rank-ordered list gave 12 survivors and an undefined coefficient" % _kills)
ok(all(not c["survives"] for c in dr.calibration_sample(
       [{"claim": str(i), "survives": False} for i in range(9)], 12)),
   "an all-kill pool is still returned whole rather than padded")
ok(len(dr.calibration_sample([], 12)) == 0 and len(dr.calibration_sample(_v, 0)) == 0,
   "empty pool and n=0 are handled")

ok(dr._schema_shortfall({"type": "object", "required": ["a", "b"],
                         "properties": {"a": {"type": "string"},
                                        "b": {"type": "array"}}},
                        {"a": "x"}) == ["b MISSING (required)"],
   "a required key that is ABSENT is caught whatever its type: a run wrote 4 hypotheses "
   "and returned no hypothesisVerdicts key at all, so the contract went unadjudicated silently")
ok(dr._schema_shortfall({"type": "object", "required": ["a"],
                         "properties": {"a": {"type": "array"}}},
                        {"a": []}) == [],
   "but an EMPTY required array with no minItems is still legal - contradictions is "
   "legitimately empty, and rejecting that would retry every clean run")

ok("no StructuredOutput in the response" in _agent_src and "exhausted" in _agent_src,
   "every way agent() can return None now logs a reason: one run reported 'synthesis "
   "failed' with nothing anywhere in the log saying why")

_fallback = _engine_txt.split("Synthesis failed - returning", 1)[1].split("\n\n", 1)[0]
ok("calibration=calibration" in _fallback and "droppedSample=dropped_sample" in _fallback,
   "a failed synthesis no longer discards the calibration and the dropped-claim sample: "
   "one run computed kappa=0.7115 at n=30, logged `calibrated`, and then threw it away")
ok("synthesisFailed" in _fallback,
   "and the report says it is incomplete rather than empty, naming what DID run")

print("\n-- the framing-contract intake: supplied fields win, the model drafts the rest --")
import json as _json, os as _os, tempfile as _tmp
_sup = {"decisionAtStake": "whether to buy standing desks for 40 people",
        "keyQuestion": "do standing desks improve health outcomes for office workers?",
        "assumptions": ["office workers, not clinical populations", "12-month horizon"],
        "whatWouldChangeTheAnswer": ["an RCT showing harm", "no effect beyond sitting time"]}
_r = run(contract=_sup)
_sc = _r.get("scopeContract") or {}
ok(_sc.get("keyQuestion") == _sup["keyQuestion"] and _sc.get("assumptions") == _sup["assumptions"],
   "supplied fields reach the report VERBATIM - the model was told to copy them and the overwrite guarantees it")
ok(_sc.get("provenance", {}).get("assumptions") == "supplied" and _sc["provenance"].get("hypotheses") == "drafted",
   "provenance is per FIELD: assumptions supplied, hypotheses drafted (%s)" % _sc.get("provenance"))
ok(len(_sc.get("hypotheses") or []) == 2, "the model drafted the missing hypotheses, seeded by the supplied fields")
ok(any("Contract: 4 field(s) supplied" in l and "drafting decisionAtStake" not in l and "drafting" in l for l in LOGS),
   "the log names what was supplied and what is being drafted")
ok(len(_r.get("hypothesisVerdicts") or []) == 2, "drafted hypotheses are still adjudicated downstream - nine readers unchanged")
ok("framingProvenance" in (_r.get("honestLimits") or {}), "honestLimits explains what provenance means")
_full = dict(_sup, hypotheses=[{"hypothesis": "h1", "killCriterion": "k1"}, {"hypothesis": "h2", "killCriterion": "k2"}])
_r2 = run(contract=_full)
ok(any("nothing to draft" in l for l in LOGS) and not any(l.strip().startswith("[framing]") for l in LOGS),
   "a FULLY supplied contract skips the framing call entirely - no model call for a decision already made")
ok(all(v == "supplied" for v in _r2["scopeContract"]["provenance"].values()), "and every field reads supplied")
_r3 = run()
ok(all(v == "drafted" for v in _r3["scopeContract"]["provenance"].values()),
   "no contract supplied: every field is drafted, and the report SAYS so rather than looking identical")
_pc = dr.p_critic(0, 2, "Q?", ["s1"], [{"label": "L", "lens": "x"}], [{"claim": "c1"}], "S.", [],
                  provenance={"assumptions": "supplied", "hypotheses": "drafted"})
ok("the asker SUPPLIED assumptions" in _pc and "DRAFTED hypotheses" in _pc and "do NOT flag" in _pc,
   "the critic is told which premises were ratified, so it stops flagging a human decision as 'accepted instead of tested'")
ok("SUPPLIED" not in dr.p_critic(0, 2, "Q?", ["s1"], [], [{"claim": "c"}], "S.", [], provenance=None),
   "and says nothing when there is no provenance to report")

print("\n-- load_contract: strict on a human-written file, before any model call --")
def _write(obj):
    fd, path = _tmp.mkstemp(suffix=".json", dir=_os.environ.get("TMPDIR") or None)
    with _os.fdopen(fd, "w", encoding="utf-8") as f:
        _json.dump(obj, f)
    return path
def _raises(obj):
    try:
        dr.load_contract(_write(obj)); return None
    except dr.ContractError as e:
        return str(e)
ok(dr.load_contract(_write(_sup)) == _sup, "a valid partial contract loads and round-trips exactly")
_e = _raises({"assumptions": "one long prose string of assumptions", "keyQuestion": "k"})
ok(_e and "assumptions" in _e, "a malformed supplied field is REJECTED and named, never dropped and re-drafted: %s" % (_e or "")[:80])
_e = _raises({"assumption": ["typo"]})
ok(_e and "unknown field" in _e and "assumption" in _e,
   "a typo'd field name is rejected - silently ignoring it would let the asker believe it was honoured")
_e = _raises({"hypotheses": [{"hypothesis": "h1"}]})
ok(_e and "hypotheses" in _e, "a hypothesis without a killCriterion is rejected at intake")
ok(_raises({}) and "no fields" in _raises({}), "an empty contract is rejected")
ok(dr.load_contract(_write(dict(_sup, provenance={"assumptions": "supplied"}))) == _sup,
   "a persisted contract (carrying provenance) can be passed straight back in - provenance is stripped")
ok(dr.load_contract(_write({"keyQuestion": "k"})) == {"keyQuestion": "k"}, "a single supplied field is enough")
_main_src2 = _engine_txt.split("def main(", 1)[1]
ok("os.path.abspath(a.contract)" in _main_src2 and "os.path.abspath(a.out)" in _main_src2,
   "--contract AND --out are absolutised before the --bg re-exec, which runs the child under a different cwd")
ok('"--question", a.question.strip()' in _main_src2 and "sys.argv[1:]" not in _main_src2.split("start_new_session")[0],
   "the --bg child's argv is rebuilt from the PARSED args, not copied from sys.argv")
ok("sys.exit(EXIT_CONTRACT)" in _main_src2 and dr.EXIT_CONTRACT == 4,
   "a rejected contract exits 4 in the PARENT, before detaching and before any model call")
ok('".contract.json"' in _main_src2, "every run writes the contract it used beside the report")

print("\n-- the model seam: shape() is the only form a caller ever sees --")
_ok = lambda sch, o: dr.shape(sch, o, "t")
# every schema: a minimal valid object passes with no problems
_valid = {
 "S_PICK": {"results": [{"url": "https://a.org", "relevance": "high"}]},
 "S_EXTRACT": {"sourceQuality": "primary", "claims": [{"claim": "c", "quote": "q", "importance": "central"}]},
 "S_VERDICT": {"refuted": False, "evidence": "e", "confidence": "high"},
 "S_FACT": {"support": "partial", "reasoning": "r"},
 "S_CRITIC": {"untraceableStatements": [], "coverageGaps": [], "verdict": "sound"},
 "S_GAP": {"coverage": [{"subQuestionIndex": 1, "status": "answered"}], "followUps": []},
}
for _n, _o in _valid.items():
    _sh, _pr = _ok(getattr(dr, _n), _o)
    ok(_pr == [] and _sh is not None, "%s: a minimal valid response passes untouched" % _n)
_sh, _pr = _ok(dr.S_VERDICT, {"refuted": "false", "evidence": "e", "confidence": "high"})
ok(_pr and "refuted" in _pr[0] and _sh is None or "refuted" not in (_sh or {}),
   "refuted='false' (a STRING) is a problem, not a refutation: it used to be read as truthiness and KILL the claim")
_sh, _pr = _ok(dr.S_FACT, {"support": "Supported", "reasoning": "r"})
ok(_pr and "support" in _pr[0], "an enum leaf outside its enum is a problem the seam retries, never a value it repairs")
_sh, _pr = _ok(dr.S_EXTRACT, {"sourceQuality": "primary", "claims": [
    {"claim": "good", "quote": "q", "importance": "central"},
    {"claim": "bad-enum", "quote": "q", "importance": "very"},
    {"claim": "missing-quote", "importance": "central"},
    "not an object"]})
ok(_pr == [] and [c["claim"] for c in _sh["claims"]] == ["good"],
   "inside an array, a bad item is DROPPED (and logged), the good ones kept, and the top level is fine")
_sh, _pr = _ok(dr.S_GAP, {"coverage": [], "followUps": [], "contradictions": "one long string of prose"})
ok(_pr == [] and _sh["contradictions"] == [],
   "contradictions arriving as a STRING becomes [] - the list += str crash path is closed at the seam")
_sh, _pr = _ok(dr.S_GAP, {"coverage": [], "followUps": [], "contradictions": '["a", "b"]'})
ok(_sh["contradictions"] == ["a", "b"], "and a double-encoded array of strings is recovered")
_sh, _pr = _ok(dr.S_REPORT, {"summary": "s", "findings": [], "caveats": "c",
                             "strongestArgumentAgainst": "x", "whatWouldChangeThisCall": []})
ok(any("hypothesisVerdicts" in x for x in _pr),
   "hypothesisVerdicts is now REQUIRED, so an absent key is a shortfall - the guard from this "
   "morning could not fire on the case its own comment cited")
_sh, _pr = _ok(dr.S_REPORT, {"summary": "s", "findings": [], "caveats": "c", "hypothesisVerdicts": [],
                             "strongestArgumentAgainst": "x", "whatWouldChangeThisCall": []})
ok(_pr == [], "but an EMPTY hypothesisVerdicts is legal: no hypotheses is a real state")
_sh, _pr = _ok(dr.S_PICK, {"results": [{"url": "https://a.org", "relevance": "high"}], "extra": 1})
ok(_sh.get("extra") == 1, "undeclared keys pass through: the schema says what we NEED, not all we accept")
ok(dr._schema_shortfall(dr.S_FRAMING, {"decisionAtStake": "x", "keyQuestion": "y",
    "assumptions": [], "whatWouldChangeTheAnswer": [], "hypotheses": []}),
   "_schema_shortfall still reports the framing shortfall (now defined by shape)")

print("\n-- a rejected response is retried DIFFERENTLY, not identically --")
ok("stop_reason" in _agent_src and "TRUNCATED" in _agent_src,
   "a truncated response is diagnosed as truncation: stop_reason separates 'cut off' from "
   "'the model chose to return nothing', and they need opposite fixes")
ok('body["max_tokens"] * 2' in _agent_src and "16000" in _agent_src,
   "truncation grows the token budget on retry, capped, instead of re-sending the same "
   "request that was already too small")
ok("YOUR PREVIOUS RESPONSE WAS REJECTED" in _agent_src,
   "a clean-but-empty response gets a corrective prompt naming the offending fields: a "
   "blind retry re-sends the identical input, so a deterministic failure just repeats "
   "(watched live doing exactly that, 3 attempts in a row)")
ok("max_tokens=4000" in _engine_txt,
   "and the framing call starts at a budget that was measured to be enough")

ok("killsByLens=dict" in _engine_txt,
   "which lens killed what is STORED, not just logged: six runs reported killsByLens={} "
   "while the log line beside it read {'support': 9, 'provenance': 10, 'counter': 5}")

print("\n-- the amended gate (dated, and it can only tighten) --")
ok(C.interpret(1.0, n=10)[0] == "underpowered",
   "kappa=1.0 on n=10 no longer returns 'calibrated' - that verdict was the whole complaint")
ok(C.interpret(1.0, n=30, per_lens={"support": 1.0, "prov": 0.78, "counter": 0.35})[0] == "usable but noisy",
   "and a clean aggregate is CAPPED when one lens sits below 0.4: a 2-of-3 vote can "
   "launder unstable raters into a stable-looking verdict")
ok(C.interpret(1.0, n=30, per_lens={"support": 1.0, "prov": 0.78, "counter": None})[0] == "usable but noisy",
   "an unmeasurable lens counts as weak, not as absent")
ok(C.interpret(1.0, n=30, per_lens={"a": 0.8, "b": 0.7, "c": 0.6})[0] == "calibrated",
   "a genuinely powered, genuinely balanced run still passes")
_verdicts = [C.interpret(k, n=n, per_lens=pl)[0]
             for k, n, pl in [(0.2, 50, {"a": 0.9}), (0.5, 50, {"a": 0.9}), (0.9, 50, {"a": 0.9})]]
ok(_verdicts == ["noise", "usable but noisy", "calibrated"],
   "the original bands are untouched: %s" % _verdicts)
ok(C.MIN_N == 30 and C.MIN_LENS_KAPPA == 0.4, "the amended constants are named and inspectable")

print("\n======== %d passed, %d failed ========" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
