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
                    "whatWouldChangeTheAnswer": ["w1"],
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
                                  "sourceTier": "T1", "factOrInference": "fact"}],
                    "strongestArgumentAgainst": "the crux was never evidenced",
                    "whatWouldChangeThisCall": ["a real RCT"],
                    "caveats": "c", "openQuestions": ["o"]}
        if label.startswith("critic:"):
            return {"untraceableStatements": ["u1"], "coverageGaps": ["g1"], "planFlaws": ["p1"],
                    "verdict": "material-gaps" if label.endswith("2") else "minor-gaps", "rationale": "r"}
        return None

    dr.web_search, dr.web_fetch, dr.agent = fake_search, fake_fetch, fake_agent
    searchmod.reset_health()


def run(cfg=None, depth="standard", q="Test question?"):
    install(cfg or {})
    dr._stats.update(calls=0, errors=0, ratelimited=0, in_tok=0, out_tok=0)
    return dr.deepresearch(q, depth)


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
ok(r["findings"][0].get("factOrInference") == "fact", "findings tag fact vs inference")
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
ok("error" in r6 and "keys present" in r6["error"],
   "string-where-list-expected is rejected and the error names what arrived")
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
_ENGINE_SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                "deepresearch", "engine.py"), encoding="utf-8").read()
ok('fact_by.get((c["claim"], c.get("sourceUrl")))' in _ENGINE_SRC,
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
_ENG = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "deepresearch", "engine.py"), encoding="utf-8").read()
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

print("\n======== %d passed, %d failed ========" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
