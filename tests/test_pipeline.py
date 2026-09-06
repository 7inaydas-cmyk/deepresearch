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

print("\n======== %d passed, %d failed ========" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
