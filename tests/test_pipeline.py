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
from deepresearch import calibration as _cal   # noqa: E402
import deepresearch as dr_pkg                  # noqa: E402

# The pipeline harness replaces dr.web_fetch with a stub and does not put it back, so
# anything wanting the REAL one has to hold a reference from before that happens.
_REAL_WEB_FETCH = dr.web_fetch
# The pipeline harness replaces dr.agent with a fixture stub and never restores it; the session-transport retry test at the foot of this file needs the real one.
_REAL_AGENT = dr.agent
_REAL_WEB_SEARCH = dr.web_search

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

    # `junk_filter` is not decoration: without it every counter-evidence call raised
    # TypeError, pmap swallowed it as a worker error and returned None, and the suite
    # went green with 90 of them printed. The lens the panel depends on most was not
    # being exercised end-to-end at all - a stale stub signature reading as coverage.
    def fake_search(q, n=6, junk_filter=True):
        if cfg.get("no_search"):
            searchmod._note("ddg-html", "fail", 0)
            return []
        searchmod._note("crossref", "ok", 3)
        if cfg.get("rescue_marker", "SQ3") in q or "rescue" in q.lower():
            return [{"url": "https://primary-rescue.org/doc", "title": "primary", "snippet": "s"}]
        return [{"url": "https://src%d.org/p" % i, "title": "T%d" % i, "snippet": "s"} for i in range(n)]

    def fake_fetch(u, cap=14000, fresh=False):
        # `fresh` must be accepted: the citation audit re-fetches rather than re-reading
        # the cache, and a stub at this seam has to carry the real interface or the audit
        # silently returns nothing — which is exactly how this surfaced.
        return "" if cfg.get("empty_pages") else "page body for " + u

    def fake_agent(prompt, schema, label="", model=None, max_tokens=0, retries=3):
        # Route every fixture through the SEAM, so the pipeline tests see exactly what a
        # production caller sees. The guards those callers used to carry are gone; if a
        # fixture is malformed the stub now returns None the way agent() would.
        #
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
                                   {"hypothesis": "h2", "killCriterion": "k2"}],
                    "needsGeneralWeb": True}
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
                        {"hypothesis": "h1", "hypothesisNumber": 1, "verdict": "killed", "killCriterion": "k1",
                         "reasoning": "claim [0] triggers it", "claimsCited": [0]},
                        {"hypothesis": "h2", "hypothesisNumber": 2, "verdict": "untested", "killCriterion": "k2",
                         "reasoning": "no confirmed claim bears on it"}],
                    # The shape a real run produced: a cross-reference to the field
                    # itself. `pointer_steelman` reproduces it; `pointer_steelman_hard`
                    # makes the re-ask fail too, so the disclosure path is exercised.
                    "strongestArgumentAgainst": (
                        "See strongestArgumentAgainst field above (duplicate not needed)."
                        if cfg.get("pointer_steelman") or cfg.get("pointer_steelman_hard")
                        else "the crux was never evidenced"),
                    "whatWouldChangeThisCall": ["a real RCT"],
                    "caveats": "c", "openQuestions": ["o"]}
        if label == "steelman-retry":
            if cfg.get("pointer_steelman_hard"):
                return {"strongestArgumentAgainst": "See above."}
            return {"strongestArgumentAgainst":
                    "The two crossover trials that carry this conclusion recruited from one "
                    "university, and selection into them plausibly tracks the outcome measured, "
                    "so the pooled estimate may be one population counted twice."}
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
# That assertion only ever covered the HARMLESS ordering, with the untrusted host first,
# where the regex happens to be right. Reversed, it is wrong: the regex reads
# `nature.com` out of `https://nature.com\@evil.example/x` while urllib - the parser the
# fetcher itself uses - reads `evil.example`. So the URL graded T2, peer-reviewed
# journal, while the page would be served by evil.example. Tiering is the one thing this
# project grades in code rather than by vibes.
ok(tiers.host_of("https://nature.com\\@evil.example/x") == "nature.com"
   and tiers.host_is_ambiguous("https://nature.com\\@evil.example/x"),
   "the reversed ordering IS ambiguous: the two parsers read two different hosts")
ok(tiers.tier_of("https://nature.com\\@evil.example/x")[0] == "T5"
   and tiers.tier_of("https://evil.com\\@trusted.org/x")[0] == "T5",
   "so both orderings are EXCLUDED rather than graded on a guess - a URL two parsers "
   "disagree about has no single host, and the cost of picking wrong is a content farm "
   "published as a journal")
for _good in ("https://www.nature.com/articles/x", "https://nature.com/x",
              "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/", "https://nber.org:443/p?x=1",
              "https://user:pw@example.org/p", "https://example.org/path\\with\\backslash",
              "https://sub.domain.example.co.uk/a/b"):
    ok(not tiers.host_is_ambiguous(_good),
       "and an ordinary URL is untouched: %s" % _good[:52])
ok(not tiers.host_is_ambiguous("https://\u0430mazon.com/idn"),
   "an IDN host is not flagged for being SPELLED differently by the two parsers - that "
   "is one host in two encodings, not two hosts")
ok(searchmod.doi_of("https://doi.org/10.1038/nature12373") == "10.1038/nature12373",
   "DOI extracted from a resolver URL")
# The pattern used `\S+`, which swallowed the fragment and the query. A link to
# `#abstract`, or a `?utm_source=` tag, produced a DOI Crossref could not resolve - and
# because doi.org is a resolver rather than a fetchable page, the source was then lost
# outright. The sibling pattern doi_in_url had always excluded both.
ok(searchmod.doi_of("https://doi.org/10.1038/x#abstract") == "10.1038/x"
   and searchmod.doi_of("https://doi.org/10.1038/x?utm_source=news") == "10.1038/x",
   "a fragment or a tracking parameter does not corrupt the DOI")
ok(searchmod.doi_of("https://doi.org/10.1038/x#abstract")
   == searchmod.doi_in_url("https://doi.org/10.1038/x#abstract"),
   "and the two DOI extractors agree, which is why one was wrong for as long as nobody "
   "compared them")
ok(searchmod.doi_of("https://doi.org/10.1038/a.b-c_d/e") == "10.1038/a.b-c_d/e",
   "a legitimate DOI with dots, dashes and slashes is still extracted whole")
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

print("\n-- depth budgets --")
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

print("\n-- how much evidence the report rests on, on EVERY exit --")
# honestLimits itself once shipped on 2 of 6 exits, so this is asserted across the
# exits rather than on the happy path alone.
for _name, _r in (("happy path", r), ("all claims killed", r3),
                  ("synthesis failed", r11), ("killed at quick depth", r12)):
    _eb = ((_r.get("honestLimits") or {}).get("evidenceBase") or {})
    ok(isinstance(_eb, dict) and isinstance(_eb.get("citableSources"), int)
       and isinstance(_eb.get("thin"), bool),
       "%s: evidenceBase carries a real source count and a thin flag" % _name)
ok(dr._evidence_base([{"tier": "T2", "claims": 1}] * 2)["thin"] is True
   and dr._evidence_base([{"tier": "T2", "claims": 1}] * dr.MIN_CITABLE_SOURCES)["thin"] is False
   and dr._evidence_base([{"tier": "T5", "claims": 3}] * 20)["citableSources"] == 0,
   "the floor is %d citable sources, and it is a label rather than an abort - the "
   "thinnest run on record was thin because of a PDF bug, and aborting it would have "
   "hidden the bug" % dr.MIN_CITABLE_SOURCES)
print("\n-- how a page was READ reaches the judgements about it --")
# _fetch_meta recorded `via` from the day the fetch seam was instrumented, and NOTHING
# that makes a judgement read it: the panel zero references, the audit zero references.
# The engine knew it had only a citation stub and asked four models to judge as though
# it held the paper. Measured 2026-09-08 over 12 calls each: shown an EMPTY page the
# auditor says `unreachable` 12/12 (so the call buys nothing), and shown an ABSTRACT it
# says `unsupported` 12/12 - the one verdict that demotes a claim the panel passed.
_saved_meta = dict(dr._fetch_meta)
try:
    dr._fetch_meta.clear()
    dr._fetch_meta.update({
        "https://p.org/dead":     {"via": "failed", "error": "403"},
        "https://p.org/binary":   {"via": "pdf-unreadable"},
        "https://p.org/abstract": {"via": "crossref-fallback", "abstractOnly": True},
        "https://p.org/archived": {"via": "wayback", "snapshotDate": "20250707101147"},
        "https://p.org/normal":   {"via": "http"},
    })
    ok(dr.read_provenance("https://p.org/dead", "text")[0] is False
       and dr.read_provenance("https://p.org/binary", "text")[0] is False,
       "a failed fetch and an unreadable PDF are UNREACHABLE in code - no model is asked "
       "to self-report an infrastructure failure the engine already observed")
    ok(dr.read_provenance("https://p.org/normal", "")[0] is False,
       "and an empty page is unreachable whatever `via` says")
    ok(dr.read_provenance("https://p.org/normal", "real text")[0] is True
       and dr.read_provenance("https://p.org/normal", "real text")[2] == "",
       "an ordinary page is reachable and adds NOTHING to the prompt, so the common path "
       "is byte-identical to before")
    _abs = dr.read_provenance("https://p.org/abstract", "stub text")
    ok(_abs[0] is True and "ABSTRACT ONLY" in _abs[2] and "`unreachable`, NOT `unsupported`" in _abs[2],
       "an abstract-only page IS judged, but the auditor is told what it is holding and "
       "told which verdict an infrastructure limit deserves")
    _wb = dr.read_provenance("https://p.org/archived", "text")
    ok(_wb[0] is True and "20250707101147" in _wb[2],
       "an archived copy carries its snapshot date, because the provenance lens judges "
       "recency and an archive is as old as its capture")
    ok(dr.read_provenance("https://p.org/unknown-url", "text") == (True, "", ""),
       "a URL with no recorded provenance is not treated as suspect")
    _p = dr.p_fact("c", "https://p.org/abstract", "stub", _abs[2])
    ok("ABSTRACT ONLY" in _p and dr.p_fact("c", "u", "t") == dr.p_fact("c", "u", "t", ""),
       "the note reaches the audit prompt, and no note leaves that prompt unchanged")
finally:
    dr._fetch_meta.clear(); dr._fetch_meta.update(_saved_meta)

print("\n-- the gate refuses impossible input instead of passing it --")
ok(_cal.interpret(1.5, n=30)[0] == "undefined"
   and _cal.interpret(-1.5, n=30)[0] == "undefined",
   "a kappa outside [-1, 1] is an arithmetic impossibility, so it is a defect upstream, "
   "not a strong result - it used to return `calibrated`")
ok(_cal.interpret(1.0, n=30)[0] == "calibrated"
   and _cal.interpret(-1.0, n=30)[0] == "noise",
   "and the legitimate endpoints still adjudicate normally")
_empty = _cal.agreement([], [])
ok(_empty["n"] == 0 and _empty["cohenKappa"] is None and _empty["verdictFlips"] == 0,
   "agreement on an empty pool reports undefined rather than raising KeyError - a "
   "module whose contract is 'never coerce, never blow up' must not blow up")

print("\n-- a model quoting text back is quoting the webtext VIEW of it --")
# The same asymmetry as the quote matcher, in two more places. The critic is shown
# webtext(summary): quote lookalikes DELETED, whitespace collapsed. Matching its
# verbatim copy with a plain `in` against the raw summary misses on any summary
# containing a quotation mark, which is most of them - and that is why `policy: strike`
# could flag nine untraceable statements and remove none.
_raw_sum = ('Trials show gains. The pilot reported a \u201c13% rise\u201d in output '
            'across all teams. Costs fell.')
_frag = "The pilot reported a 13% rise in output across all teams."
ok(_frag in dr.webtext(_raw_sum), "the critic really is shown the fragment")
ok(_frag not in _raw_sum, "and a plain substring test against the raw summary fails")
ok(dr.webtext_pattern(_frag).search(_raw_sum) is not None,
   "the tolerant pattern finds it, so the strike policy can actually strike")
ok(dr.webtext_pattern("Something never written here at all").search(_raw_sum) is None,
   "and it is NOT fuzzy: text that is absent still does not match")
_nl = "Trials show gains. The pilot reported\na 13% rise in output. Costs fell."
ok(dr.webtext_pattern("The pilot reported a 13% rise in output.").search(_nl) is not None,
   "a newline the critic saw as a space is matched too")

print("\n-- a picked URL is matched against the form the model was SHOWN --")
# The pick list renders each hit as webtext(url, 200), which appends an ellipsis when it
# truncates. For a URL over 200 characters the model faithfully copies a string that can
# never match the original, and a good source is dropped for obeying "copy each url
# EXACTLY as given".
_long = "https://www.ncbi.nlm.nih.gov/pmc/articles/" + "/".join(
    "section-%d-of-the-document" % i for i in range(9)) + "/full.pdf"
ok(len(_long) > 200, "the fixture URL is long enough to be truncated: %d chars" % len(_long))
_shown = dr.webtext(_long, 200)
ok(dr.norm_url(_shown) != dr.norm_url(_long),
   "a faithful copy of the truncated form does NOT match the original")
_by = {}
for _h in [{"url": _long, "title": "t", "snippet": "s"}]:
    _by[dr.norm_url(_h["url"])] = _h
    _by.setdefault(dr.norm_url(dr.webtext(_h["url"], 200)), _h)
ok(_by.get(dr.norm_url(_shown)) is not None
   and _by[dr.norm_url(_shown)]["url"] == _long,
   "indexing by both forms resolves it, and resolves to the REAL url")
ok('by_url.setdefault(norm_url(webtext(h["url"], 200)), h)'
   in open(dr.__file__, encoding="utf-8").read(),
   "and the engine's picker does exactly that")

print("\n-- no schema field is demanded of a model and then never read --")
# The bug class this project keeps rediscovering. Three instances found on 2026-09-08
# alone: `locatedQuote` (the auditor's own verbatim pull, ~30 calls a run, read by
# nothing), `counterSource` (the source the counter lens names as contradicting a
# claim), and the second refuter's evidence on a 2-1 kill. Every one cost output
# tokens on every call and reached no reader.
_SPREAD_THROUGH = {
    # S_REPORT is merged wholesale into the report with `out.update(report)`, so its
    # fields reach the reader without any individual read. That is intended.
    "S_REPORT",
}
_EXEMPT = {
    # field -> why it is legitimately unread
    "strategy": "the planner's one-line framing; published inside the plan, never branched on",
    "reason": "S_GAP followUps[].reason explains a follow-up query to the reader of the log",
    "note": "S_GAP coverage[].note travels to the report inside `coverage`",
    "subQuestionIndex": "positional key used to build coverage rows",
    "rationale": "read via uniq()/list comprehension over critique rows",
    "confidence": "read through best.get('confidence') on the sorted verdict list",
}
def _schema_props(sch, out=None):
    out = out if out is not None else set()
    if not isinstance(sch, dict):
        return out
    for k, v in (sch.get("properties") or {}).items():
        out.add(k); _schema_props(v, out)
    if "items" in sch:
        _schema_props(sch["items"], out)
    return out

_engine_src = open(dr.__file__, encoding="utf-8").read()
_unread = []
for _name in sorted(n for n in dir(dr) if n.startswith("S_")):
    if _name in _SPREAD_THROUGH:
        continue
    _sch = getattr(dr, _name)
    if not isinstance(_sch, dict):
        continue
    for _f in sorted(_schema_props(_sch)):
        if _f in _EXEMPT:
            continue
        # any read: subscript, .get(), or a string key handed to a helper like uniq()
        if _re.search(r'\["%s"\]|\.get\("%s"|uniq\("%s"|"%s":\s*(?:webtext|\[)' % (_f, _f, _f, _f), _engine_src):
            continue
        _unread.append("%s.%s" % (_name, _f))
ok(not _unread,
   "every schema field is read back somewhere, or exempted with a reason. Unread: %s"
   % (", ".join(_unread) or "none"))

print("\n-- a killed claim says what killed it --")
_killed = (r3.get("refuted") or [])
ok(_killed and all("refutedBy" in k for k in _killed),
   "every refuted row lists EVERY refuter, not just the first - a 2-1 kill used to "
   "discard the second refuter's reason entirely")
ok(all(isinstance(k.get("contradictedBy"), list) for k in _killed),
   "and carries the counter-sources the counter-evidence lens named, which the schema "
   "demanded on every call and no code read")
# There were TWO to_ref definitions - one in the run function and a drifted lambda
# inside _synthesize - so fixing one left the happy path on the old shape. Compare the
# exits rather than trusting that a single definition stayed single.
_ref_keys = {}
for _n, _r in (("happy path", r), ("all killed", r3), ("synthesis failed", r11),
               ("killed at quick depth", r12)):
    _rows = _r.get("refuted") or []
    if _rows:
        _ref_keys[_n] = tuple(sorted(_rows[0].keys()))
ok(len(set(_ref_keys.values())) == 1 and len(_ref_keys) >= 2,
   "every exit builds refuted rows with the SAME keys (%d exits checked): %s"
   % (len(_ref_keys), ", ".join(sorted(set(_ref_keys.values()))[0]) if _ref_keys else "none"))

print("\n-- tag recovery is worthless unless it survives its CONSUMER --")
# 332 tests were green on a commit where framing died end to end. The tests asserted
# as_list('<item>a</item>...') == ['a', ...] - the plumbing - and never that shape()
# does anything useful with those items on an object-typed array. The test right above
# this one even used <hypothesis>, the exact field that broke, and checked only the half
# that worked. So: every array-of-object field, driven from a table.
def _minimal(schema, skip):
    """An object satisfying every required field of `schema` except `skip`."""
    out = {}
    for k in (schema.get("required") or []):
        if k == skip:
            continue
        spec = (schema.get("properties") or {}).get(k) or {}
        t = spec.get("type")
        if "enum" in spec:      out[k] = spec["enum"][0]
        elif t == "array":
            n = spec.get("minItems") or 1
            it = (spec.get("items") or {}).get("type")
            out[k] = ([_minimal(spec["items"], None) for _ in range(n)] if it == "object"
                      else ["x%d" % i for i in range(n)])
        elif t == "integer":    out[k] = 0
        elif t == "boolean":    out[k] = False
        elif t == "object":     out[k] = _minimal(spec, None)
        else:                   out[k] = "x"
    return out

_OBJ_ARRAYS = []
for _n in sorted(x for x in dir(dr) if x.startswith("S_")):
    _sc = getattr(dr, _n)
    if not isinstance(_sc, dict):
        continue
    for _f, _sp in (_sc.get("properties") or {}).items():
        if isinstance(_sp, dict) and _sp.get("type") == "array" \
           and (_sp.get("items") or {}).get("type") == "object":
            _OBJ_ARRAYS.append((_n, _sc, _f, _sp))
ok(len(_OBJ_ARRAYS) == 8,
   "every array-of-object field is covered by this table: %d found" % len(_OBJ_ARRAYS))

for _n, _sc, _f, _sp in _OBJ_ARRAYS:
    _need = _sp.get("minItems") or 2
    _payload = "".join("<item>recovered text %d for this field</item>" % i for i in range(_need))
    _obj = _minimal(_sc, _f); _obj[_f] = _payload
    _shaped, _probs = dr.shape(_sc, _obj, "t")
    _joined = " | ".join(_probs)
    _req = ", ".join((_sp.get("items") or {}).get("required") or [])
    ok(any("bare strings" in p for p in _probs),
       "%s.%s: a tag-recovered payload is reported as recovered-but-unusable, not as a "
       "bare shortfall" % (_n, _f))
    ok("recovered text 0" in _joined and (not _req or _req.split(", ")[0] in _joined),
       "%s.%s: and the retry is told WHAT arrived and WHICH keys were needed, so it is "
       "not the identical re-ask that burned all five attempts" % (_n, _f))

# The narrowing that the pre-existing drop-a-bad-item test caught. A bare string beside
# enough good objects is still just a malformed item: logged, dropped, no retry forced.
_shaped, _probs = dr.shape(dr.S_EXTRACT, {"sourceQuality": "primary", "claims": [
    {"claim": "good", "quote": "q", "importance": "central"}, "not an object"]}, "t")
ok(_probs == [] and [c["claim"] for c in _shaped["claims"]] == ["good"],
   "but a bare string beside surviving objects forces NO retry - the informed path fires "
   "only when the loss actually costs the array")

# Mapping a bare string onto the item's single required key was the obvious fix and it
# cannot work here: not one of the eight declares fewer than two required keys.
ok(all(len(((_sp.get("items") or {}).get("required") or [])) >= 2
       for _n, _sc, _f, _sp in _OBJ_ARRAYS),
   "and every one of the 8 requires >=2 keys, so a bare string can never satisfy one on "
   "its own - which is why the fix is an informed retry, not a mapping")

print("\n-- a verdict never claims a hypothesis the contract did not hold --")
ok('_v["preRegistered"] = ' in _engine_src,
   "every hypothesisVerdict is stamped with whether its hypothesis was registered BEFORE "
   "the search - it used to be published unstamped, beside a caveat asserting the field "
   "was empty")
ok("postHocHypotheses" in _engine_src and "not a test of anything" in _engine_src,
   "and a post-hoc verdict raises its own honest limit rather than passing as a "
   "pre-registered adjudication")
# From a real run, 2026-09-08. Framing registered these; synthesis adjudicated the same
# four and relabelled them "H1:".."H4:". A first version of this matcher truncated BOTH
# sides to 80 chars before testing containment, so the 4-character prefix shifted the
# alignment and all four were stamped post-hoc — the report then asserted that four
# pre-registered hypotheses had been invented after the evidence.
_REG = "Nudges remain broadly effective: bias-corrected effect sizes are attenuated but still meaningfully positive"
_VER = "H1: Nudges remain broadly effective: bias-corrected effect sizes are attenuated but still meaningfully positive"
ok(dr._same_hypothesis(dr._hyp_key(_VER), dr._hyp_key(_REG)),
   "an 'H1:' relabelling still matches its registered hypothesis - comparing two "
   "truncated strings for containment can never work when a prefix shifts them")
# Attempt 2 also shipped a false stamp: a 60-character probe. These are the VERBATIM
# strings from the run that exposed it - not a fixture, because a fixture is something I
# could shape until it passed, and typing an approximation of these is exactly how the
# first version of this test went green on data the engine had never seen.
_R4 = ("The debate is largely a definitional/measurement artifact: 'deliberate practice' "
       "as narrowly defined by Ericsson is hard to measure reliably, so disagreements "
       "stem from methodology rather than a true underlying difference in effect size.")
_V4 = ("H4: The debate is largely a definitional/measurement artifact rather than a true "
       "underlying difference in effect size.")
_R3 = ("The effect of deliberate practice is genuinely overstated: other factors (innate "
       "ability/genetics, starting age, working memory, cumulative non-deliberate "
       "experience) explain more variance than practice itself once properly controlled.")
_V3 = ("H3: The effect is genuinely overstated because other factors (genetics, starting "
       "age, working memory, cumulative non-deliberate experience) explain more variance "
       "than practice once properly controlled.")
ok(dr._same_hypothesis(dr._hyp_key(_V4), dr._hyp_key(_R4)),
   "rewording that starts 56 characters in still matches - a 60-character probe missed "
   "exactly this, and prefix matching will always miss somewhere")
ok(dr._same_hypothesis(dr._hyp_key(_V3), dr._hyp_key(_R3)),
   "and so does rewording in the middle of the sentence")
ok(not dr._same_hypothesis(dr._hyp_key(_V4), dr._hyp_key(_R3))
   and not dr._same_hypothesis(dr._hyp_key(_V3), dr._hyp_key(_R4)),
   "while two DIFFERENT hypotheses from that same run still do not match each other - "
   "measured separation was 0.95-1.00 for true pairs against 0.22 for cross pairs")
ok(dr.HYP_MATCH_THRESHOLD == 0.65,
   "the threshold is the measured mid-gap, not a guess: %s" % dr.HYP_MATCH_THRESHOLD)
ok(not dr._same_hypothesis(dr._hyp_key("H9: something nobody ever registered anywhere"),
                           dr._hyp_key(_REG)),
   "but a genuinely invented hypothesis does NOT match - the stamp has to mean something")
ok(not dr._same_hypothesis("", dr._hyp_key(_REG)) and not dr._same_hypothesis(dr._hyp_key(_REG), ""),
   "and an empty side never matches, so a missing hypothesis is never called pre-registered")
ok("NOTHING here was pre-registered" in _engine_src,
   "the no-contract caveat now describes what the field actually holds, instead of "
   "asserting it is empty while it is not")

print("\n-- the audited attacks, as regressions --")
# Every check below was defeated by an input its own calibration never pointed at. These
# are the auditor's inputs verbatim, not fixtures chosen by the author of the fix: an
# instrument calibrated only on the failure it was built for keeps passing the adjacent one.

# F1 — an ellipsis used to launder a quote stitched from two sections, in EITHER order,
# to `located-elided` at foundFraction 1.0, while the same two sentences without the
# ellipsis scored `partial`.
_STITCH_PAGE = ("Results. Profits rose 3 percent in the trial arm. " + ("filler sentence. " * 40)
                + "Discussion. The company will file for bankruptcy next quarter.")
for _lbl, _q in (
    ("forward", "Profits rose 3 percent in the trial arm. ... The company will file for bankruptcy next quarter."),
    ("reversed", "The company will file for bankruptcy next quarter. ... Profits rose 3 percent in the trial arm."),
):
    _r = dr.quote_span(_STITCH_PAGE, _q)
    ok(_r["status"] not in dr.QUOTE_ON_PAGE,
       "a quote stitched across sections is NOT laundered by an ellipsis (%s): %s"
       % (_lbl, _r["status"]))
_honest = ("The trial found that profits rose 3 percent in the treated arm, a result the authors "
           "attribute to scheduling effects rather than headcount, and the effect persisted at 12 months.")
ok(dr.quote_span(_honest, "profits rose 3 percent in the treated arm ... the effect persisted at 12 months"
                 )["status"] == "located-elided",
   "while an honest elision inside one passage still passes - the bound is on how far the "
   "fragments sit apart, not on the ellipsis itself")

# F2 — a post-hoc SUPERSET of a registered hypothesis contains it as a substring and
# carries all its content words, so min()-denominator overlap scored it 1.0 and stamped
# it pre-registered. That is the exact failure the stamp exists to prevent.
for _reg, _post in (
    ("Minimum wage increases reduce employment",
     "Minimum wage increases reduce employment, and the reduction persists for at least a decade after passage"),
    ("Standing desks improve health outcomes",
     "Standing desks improve health outcomes, productivity and mood across every industry and country studied"),
):
    ok(not dr._same_hypothesis(dr._hyp_key(_post), dr._hyp_key(_reg)),
       "a post-hoc superset is NOT stamped pre-registered: %r" % _post[:56])
# The character fallback that used to rescue those terse pairs is GONE, in both builds.
# It was calibrated on rewordings and never on the mirror: a negation is a tiny edit that
# INVERTS the meaning, so it certified opposites as the same hypothesis.
for _a, _b in (("output is stable", "output is unstable"),
               ("the effect is real", "the effect is unreal"),
               ("prices increased", "prices decreased")):
    ok(not dr._same_hypothesis(dr._hyp_key(_a), dr._hyp_key(_b)),
       "two OPPOSITE terse hypotheses are not called the same one: %r vs %r" % (_a, _b))
ok(not dr._same_hypothesis(dr._hyp_key("The effect is nil"), dr._hyp_key("The effect is zero")),
   "and the genuine terse rewording is marked post-hoc rather than guessed at - measured "
   "across all 160 hypotheses in runs/, none is short enough to reach this path, so the "
   "fallback protected nothing while risking a false pre-registration")

# The number was authoritative with NOTHING checked, so a verdict adjudicating a
# hypothesis the run never registered was stamped pre-registered by typing a digit.
_REG_MW = [dr._hyp_key("Minimum wage increases reduce teen employment modestly in the first two years"),
           dr._hyp_key("The apparent effect is largely a publication-selection artifact in the older literature")]
ok(dr._hyp_mismatch(dr._hyp_key("The minimum wage increase caused a decade-long employment "
                                 "decline across all age groups"), _REG_MW[0]),
   "a verdict whose text adjudicates something never registered is caught, whatever "
   "number it types")
ok(not dr._hyp_mismatch(dr._hyp_key("H1: Minimum wage rises modestly lower teen employment "
                                     "over the first two years"), _REG_MW[0]),
   "while a genuine rewording that names the right number is still believed - the check "
   "overrules the number on SUBJECT, never on wording")
# The bar was 0.40, which caught only a different SUBJECT and let the round-2 superset
# back in through the number path: a verdict swapping the registered scope for a
# different one scores 0.545 and was stamped preRegistered: true BY THE NUMBER.
_MW = dr._hyp_key("Minimum wage increases reduce teen employment modestly in the first two years")
ok(dr._hyp_mismatch(dr._hyp_key("Minimum wage increases reduce teen employment only among "
                                "part-time workers"), _MW),
   "a verdict that swaps the registered scope for a different one is caught (0.545) - at "
   "the first bar of 0.40 it read as a certainty for a claim the run never registered")
ok(not dr._hyp_mismatch(dr._hyp_key("Minimum wage increases reduce teen employment"), _MW),
   "while the SUBSET still passes at 1.000 - dropping a qualifier keeps every word inside "
   "the registered hypothesis, and that is the case hypothesisNumber exists for at all")
ok(dr._HYP_MISMATCH_MAX == 0.65,
   "the bar sits in the measured gap 0.545-0.727, not above it: a first attempt at 0.75 "
   "caught a genuine rewording that is one of the contract's own good references, and the "
   "structural rule failed the build rather than letting the overcorrection ship (bar=%s)"
   % dr._HYP_MISMATCH_MAX)

# F4 — the thinness gate counted fetched-and-citable URLs, so five paywalled shells that
# produced nothing read as a healthy evidence base on the one field callers gate on.
ok(dr._evidence_base([{"tier": "T2", "claims": 0}] * 5)["thin"] is True,
   "five citable sources that yielded NO claims are thin, not an evidence base")
ok(dr._evidence_base([{"tier": "T2", "claims": 1}] * 2 + [{"tier": "T2", "claims": 0}] * 3
                     )["citableSources"] == 2,
   "and only the sources that actually produced a claim are counted")

# F3 — the probe credited a planted sentence when ANY of its first six long words
# appeared anywhere in the flagged text, and those words are the ordinary vocabulary of
# critique. A critic naming nothing scored 3 of 3.
from deepresearch import probes as _P   # noqa: E402
_PL = [{"kind": "k%d" % i, "text": t} for i, t in enumerate([
    "The summary says the findings were confirmed across multiple studies.",
    "Evidence points to a large effect across studies.",
    "The effect across studies is consistent and confirmed."])]
_GENERIC = ["The summary says the findings were confirmed, but claim [3] only reports a projection.",
            "Evidence points one way while the conclusion points another.",
            "The effect across studies is described without a base rate."]
_r = _P.score_critic_probes(_PL, _GENERIC, "material-gaps", "material-gaps", clean_flagged=_GENERIC)
ok(_r["detectionRate"] == 0.0,
   "a critic that names NO planted sentence scores zero, even when its true generic "
   "objections share the planted vocabulary: %s" % _r["detectionRate"])
_r2 = _P.score_critic_probes(_PL, [p["text"] for p in _PL], "minor-gaps", "material-gaps",
                            clean_flagged=_GENERIC)
ok(_r2["detectionRate"] == 1.0,
   "while a critic that actually reproduces them scores them all")
ok(_r2["falsePositiveFloor"] == 0.0 and "above falsePositiveFloor" in _r2["floorNote"],
   "and a clean arm is reported beside it - a detection rate with no control arm is not "
   "evidence of detection")
ok(_P.score_critic_probes(_PL, [], "a", "b")["falsePositiveFloor"] is None,
   "an uncontrolled run says so rather than implying a floor of zero")

# F7 — a lens call lost to a 429 made survives=False by quorum, so an infrastructure
# failure entered the kappa vectors as a verdict flip.
_eng_src = open(dr.__file__, encoding="utf-8").read()
ok('if c.get("erroredVotes") or d.get("erroredVotes"):' in _eng_src,
   "claims whose lens calls errored in either pass are excluded from the calibration "
   "vectors - an HTTP 429 is not a changed mind")
ok('"excludedForLensErrors"' in _eng_src and '"scope"' in _eng_src,
   "and the count and scope are published, so the exclusion is visible rather than silent")

# S4 — the integer leaf was the one place violating ADR-0001. int() accepted True as 1,
# "5" as 5 and 3.7 as 3, and a fractional subQuestionIndex lands a coverage row in the
# wrong bucket without a word.
_isch = {"type": "object", "required": ["i"], "properties": {"i": {"type": "integer"}}}
_int = lambda v: dr.shape(_isch, {"i": v}, "t")
ok(_int(3)[0]["i"] == 3 and _int(3.0)[0]["i"] == 3 and not _int(3.0)[1],
   "a real integer passes, and so does an integral float - JSON has no int/float "
   "distinction and 3.0 IS 3, so accepting it loses nothing")
for _bad, _why in ((True, "a boolean"), (False, "a boolean"), (3.7, "a fractional float"),
                   ("5", "a string"), ("x", "not a number")):
    ok(bool(_int(_bad)[1]),
       "%r is a problem the seam retries, not a value it repairs (%s)" % (_bad, _why))
ok("is a boolean, not an integer" in _int(True)[1][0],
   "and a bool says so by name - isinstance(True, int) is True in Python, which is how "
   "this slipped through")

# S6 — a failed audit call was filtered out of fact_rows with no counter, so the headline
# denominator shrank silently exactly when the run was rate-limited.
_src = open(dr.__file__, encoding="utf-8").read()
ok('"auditErrors": audit_errors' in _src and "audit_errors = len(_audit_out)" in _src,
   "audit calls that returned nothing are counted and published, not dropped in silence")
ok("are NOT in the denominator" in _src,
   "and the scope string states the real denominator rather than implying the full pool")

# S2 — relevant() guarded ONE backend of eleven, and it guarded the one backend that is
# off on this host, so the filter against a poisoned engine was protecting nothing.
_saved_impl = dict(searchmod._IMPL)
_saved_health = dict(searchmod._health)
try:
    searchmod._IMPL["t_junk"] = lambda q, n: [
        {"url": "https://cebupacificair.com/%d" % i, "title": "Cebu Pacific booking",
         "snippet": "book flights"} for i in range(8)]
    searchmod._IMPL["t_good"] = lambda q, n: [
        {"url": "https://x.org/%d" % i, "title": "minimum wage employment effects",
         "snippet": "study"} for i in range(4)]
    searchmod._IMPL["t_chal"] = lambda q, n: (_ for _ in ()).throw(RuntimeError("challenged"))
    searchmod._health.clear()
    ok(searchmod.search("minimum wage employment", n=8, backends=["t_junk"]) == [],
       "a backend serving results about something else is filtered to nothing, whichever "
       "backend it is - the airline-results failure was on SearXNG, the filter now covers all 11")
    ok(len(searchmod.search("minimum wage employment", n=8, backends=["t_good"])) == 4,
       "while a backend serving related results is untouched")
    searchmod.search("x", n=4, backends=["t_chal"])
    _h = searchmod._health
    ok(_h["t_junk"].get("junk") == 1 and _h["t_chal"].get("challenged") == 1,
       "and searchHealth names WHICH failure: junk, challenged and fail had all been "
       "recorded identically, and they have three different fixes")
finally:
    searchmod._IMPL.clear(); searchmod._IMPL.update(_saved_impl)
    searchmod._health.clear(); searchmod._health.update(_saved_health)

# S1 — challenge detection was a two-word blocklist, so it held only for the one
# interstitial that had been measured.
for _w in ("anomaly detected", "Our systems have detected unusual traffic",
           "Please verify you are a human", "Complete the CAPTCHA", "Access Denied",
           "Too Many Requests", "bot detection triggered"):
    ok(bool(searchmod._CHALLENGE.search(_w)),
       "a challenge page worded %r is recognised" % _w[:34])
ok(not searchmod._CHALLENGE.search("Results for minimum wage employment effects"),
   "and a real results page is not mistaken for one")
ok(searchmod._LITE_MIN_RESULTS >= 2,
   "the lite fallback needs more than one anchor: it harvests ANY external link, so an "
   "interstitial carrying a single sponsor link reported ok with one result, and the "
   "selftest then printed 'general web live'")

print("\n-- the second audit: the adjacent input, again --")
# Every fix below was validated against the attack that motivated it and NOT against its
# mirror. These are the mirrors.

# The subset. The superset fix made the denominator the verdict's own tokens, which
# measures what a post-hoc hypothesis ADDS and is blind to what it DROPS. No lexical rule
# separates the two: genuine rewordings drop 8-12 content words, a qualifier-stripping
# subset drops 2. So the schema now asks for the NUMBER, and the text path is a marked
# fallback rather than the answer.
ok("hypothesisNumber" in dr.S_REPORT["properties"]["hypothesisVerdicts"]["items"]["required"],
   "the verdict must name WHICH registered hypothesis it adjudicates, so there is nothing "
   "to match and neither adding nor dropping content can fool it")
ok("hypothesisNumber" in _engine_src and "preRegisteredBy" in _engine_src,
   "and the stamp records whether it came from the number or was inferred from text - a "
   "reader can tell a certainty from a guess")

# The string leaf. `required` only ever meant key-present, so the locatedQuote fix was
# hollow: a number passed the schema exactly as an empty string did.
_ssch = {"type": "object", "required": ["s"], "properties": {"s": {"type": "string"}}}
for _bad in (123, True, ["t"], {"a": 1}):
    ok(bool(dr.shape(_ssch, {"s": _bad}, "t")[1]),
       "a declared string rejects %r - the type was never checked, in either build" % (_bad,))
ok(not dr.shape(_ssch, {"s": "real"}, "t")[1] and not dr.shape(_ssch, {"s": ""}, "t")[1],
   "while a real string passes, and an empty one still does: an auditor that legitimately "
   "found no quote must be able to say so")

# In-passage quote mining. Every word real, the refutation between them dropped.
_mine_page = ("The drug reduced mortality in the trial arm. However, the effect vanished "
              "entirely in the over-65 subgroup and the trial was unblinded. The authors "
              "recommend approval.")
_mine = dr.quote_span(_mine_page,
                      "The drug reduced mortality in the trial arm ... The authors recommend approval.")
ok(_mine["status"] == "located-elided" and _mine.get("skippedChars", 0) > 50,
   "a quote that jumps a limitation is still located - every word IS on the page - but "
   "the skip is measured: %s characters" % _mine.get("skippedChars"))
ok("STITCHED ACROSS AN ELLIPSIS" in dr._quote_line({"quoteCheck": _mine}),
   "and the panel is TOLD what was skipped, instead of 'YES, 100% of it' with no mention "
   "that a subgroup reversal sat between the fragments")

# The challenge detector fired on result CONTENT, so a due-diligence query about rate
# limiting returned zero from both DDG backends.
for _t in ("HTTP 429 Too Many Requests - Stack Overflow",
           "Why is my IP blocked by Cloudflare? - Server Fault"):
    ok(bool(searchmod._CHALLENGE.search(_t)),
       "the markers still match this text (%s)" % _t[:34])
# ...and this used to be asserted by looking for a line of SOURCE TEXT, which is how the
# next bug hid: the markers were moved behind `if not out:` while `out = lite` still ran
# unconditionally, so the source line was present and the markers were unreachable for
# exactly the one-anchor interstitial they were added for. Drive the real function.
def _ddg_body(body, query="cloudflare rate limiting"):
    _real_get = searchmod._get
    searchmod._get = lambda url, hdrs=None: body
    try:
        return searchmod._ddg(query, 6, lite=True), None
    except RuntimeError as e:
        return None, str(e)
    finally:
        searchmod._get = _real_get

_INTERSTITIAL = ('<html><title>Just a moment...</title><body><h1>Verify you are human</h1>'
                 '<p>Our systems have detected unusual traffic from your computer network.</p>'
                 '<a href="https://www.cloudflare.com/help">Cloudflare Help Center</a></body></html>')
_rows, _err = _ddg_body(_INTERSTITIAL)
ok(_err == "challenged",
   "a one-anchor interstitial is challenged, not reported as a live backend - it used to "
   "return ok/results=1 and the selftest then printed 'general web live via: ddg-lite' on "
   "a blocked host (got: %s)" % (_err or "ok, results=%d" % len(_rows or [])))

_REAL_429 = ('<html><body>' + ('<p>padding about web servers. </p>' * 80) +
             ''.join('<a href="https://example%d.org/p">HTTP 429 Too Many Requests explained</a>' % i
                     for i in range(3)) + '</body></html>')
_rows, _err = _ddg_body(_REAL_429, "HTTP 429 Too Many Requests")
ok(_err is None and len(_rows) == 3,
   "while a GENUINE results page about rate limiting still parses - the markers describe "
   "the page, and on a page that produced results they are describing a result (got: %s)"
   % (_err or "%d results" % len(_rows)))

_SPARSE = ('<html><body>' + ('<p>a thin but real results page on widget pricing. </p>' * 80) +
           '<a href="https://example.org/only">The one relevant page on widget pricing</a></body></html>')
_rows, _err = _ddg_body(_SPARSE, "widget pricing")
ok(_err is None and len(_rows) == 1,
   "and a real SPARSE page keeps its single result: one anchor is weak evidence either "
   "way, so the markers decide rather than a count alone (got: %s)"
   % (_err or "%d results" % len(_rows)))

# The junk filter starved the counter-evidence lens: a contradiction routinely shares no
# vocabulary with the claim it contradicts.
import inspect as _insp2   # noqa: E402
ok("junk_filter" in _insp2.signature(_REAL_WEB_SEARCH).parameters
   and "junk_filter=False" in _engine_src,
   "the counter-evidence hunt opts out of the shared-word filter - 'New Jersey diner "
   "survey finds hours unchanged' shares nothing with 'the minimum wage reduces teen "
   "employment', and dropping it told the lens the web was silent")

# S3/S5 — the two the audit listed as still open and unclaimed.
ok("untraceableCountMeans" in _engine_src and "not distinct problems" in _engine_src,
   "untraceableCount says what it counts: distinct flagged STRINGS, not distinct "
   "problems. Deduplicating by meaning needs a semantic judgement, and this codebase has "
   "now twice learned not to solve that with a similarity threshold")
_norm_dupes = [{"untraceableStatements": ["The summary says X."]},
               {"untraceableStatements": ["the summary says  x"]}]
_saved = globals().get("crits")
ok(len({_re.sub(r"\s+", " ", x).strip().lower().rstrip(".")
        for c in _norm_dupes for x in c["untraceableStatements"]}) == 1,
   "and the mechanical duplicates DO collapse - whitespace, case and a trailing period")
_js_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "integrations/claude-code/deepresearch.js"), encoding="utf-8").read()
ok("agentCalls: AGENT_CALLS" in _js_src and "AGENT_CALLS++" in _js_src,
   "the JS build COUNTS agent calls instead of computing a plausible number from array "
   "lengths - the formula could not see a retry, a skip or a failure")

print("\n-- the version is declared in three files and they must agree --")
# Three copies of one fact, with nothing checking them. The same shape as the tier
# rules, which sat out of sync between the two runtimes while the marker test passed.
# `pip show` reads pyproject, `deepresearch.__version__` reads the package, and the
# Hermes skill loader reads its own frontmatter - so a bump that misses one leaves a
# consumer reporting a version it is not running.
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
def _declared():
    out = {}
    out["pyproject.toml"] = _re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        open(os.path.join(_root, "pyproject.toml"), encoding="utf-8").read()).group(1)
    out["deepresearch/__init__.py"] = dr_pkg.__version__
    out["integrations/hermes/SKILL.md"] = _re.search(
        r"(?m)^version:\s*(\S+)",
        open(os.path.join(_root, "integrations/hermes/SKILL.md"), encoding="utf-8").read()).group(1)
    return out
_vs = _declared()
ok(len(set(_vs.values())) == 1,
   "every declared version agrees: %s" % ", ".join("%s=%s" % kv for kv in sorted(_vs.items())))
ok(_re.fullmatch(r"\d+\.\d+\.\d+", dr_pkg.__version__) is not None,
   "and it is a real semantic version: %s" % dr_pkg.__version__)

print("\n-- unreadable extraction is refused, not passed to a model --")
ok(searchmod.is_prose("the quick brown fox jumps over the lazy dog and this is prose "
                      * 30)[0],
   "ordinary English prose passes the gate")
_garbage = "".join(chr(1) + chr(15) + "$*-,)" for _ in range(2000))
ok(not searchmod.is_prose(_garbage)[0],
   "a PDF whose font encoding defeats extraction is refused: 13% letters and zero "
   "stopwords, and a model shown it returned four fluent invented quotes")
ok(searchmod.is_prose("Les resultats montrent que le salaire minimum affecte "
                      "l emploi des jeunes travailleurs dans cette region " * 20)[0],
   "a non-English paper is NOT thrown away as binary: both signals must fail, and a "
   "French page has a high letter ratio with no English stopwords")
_ok, _why, _sig = searchmod.is_prose(_garbage)
ok("letterRatio" in _sig and "stopwordsPerKchar" in _sig and "pdfWords" in _sig,
   "and the refusal reports every number it measured, whichever test it failed")
# The length floor is the ORIGINAL guard. Dropping it when the ratio signals were added
# was a regression: is_prose("a") returned True, because a one-character page is 100%
# letters. A title-only extraction is perfectly good prose and still is not a page.
ok(not searchmod.is_prose("a")[0] and not searchmod.is_prose("word " * 39)[0]
   and searchmod.is_prose("words " * 40)[0],
   "under %d words is refused however clean it reads - the ratio signals catch binary, "
   "they cannot catch a PDF that extracted to its title" % searchmod.MIN_PDF_WORDS)
# Garbage long enough to clear the word floor must still fail on the ratios, and say so.
_wordy_garbage = "x$*- " * 200
_ok2, _why2, _sig2 = searchmod.is_prose(_wordy_garbage)
ok(not _ok2 and "%" in _why2 and "stopwords" in _why2,
   "binary that clears the word floor is refused on the ratios, naming both: %s"
   % _why2[:70])

print("\n-- a blocked publisher falls back to the archive, labelled --")
ok(searchmod.wayback_snapshot.__doc__ and "id_" in searchmod.wayback_snapshot.__doc__,
   "the raw-capture modifier is documented: without it the snapshot arrives wrapped in "
   "the archive's own toolbar, which a model will quote as page text")
ok(searchmod._WB_CHROME.search("The Wayback Machine - http://web.archive.org/")
   and searchmod._WB_CHROME.search("Organization: Archive Team Formed in 2009"),
   "archive furniture is recognised, so a snapshot that came back as the archive's own "
   "page is refused rather than extracted - it is fluent English and passes the prose gate")
ok(not searchmod._WB_CHROME.search("No evidence for nudging after adjusting for "
                                   "publication bias | PNAS Contents Thaler and Sunstein"),
   "and a real archived paper is not mistaken for furniture")

print("\n-- the quote is located in code, not asserted in a prompt --")
_PAGE = ("Researchers found that productivity rose 13 percent over six months, and the "
         "effect persisted through the follow-up period. Separately, attrition fell by half.")
ok(dr.quote_span(_PAGE, "productivity rose 13 percent over six months")["status"] == "located",
   "an exact quote is located")
ok(dr.quote_span(_PAGE, "productivity   rose 13\n percent over  six months")["status"] == "located",
   "whitespace and line breaks do not break a real quote")
ok(dr.quote_span(_PAGE, "\u201cproductivity rose 13 percent over six months\u201d")["status"] == "located",
   "smart quotes, ligatures and non-breaking spaces are normalised away")
ok(dr.quote_span(_PAGE, "productivity rose 13 percent ... attrition fell by half")["status"]
   == "located-elided",
   "an ellipsis is honest quoting of a long passage, not evasion")
# THE invariant. The model is shown webtext(page), never the raw page: webtext DELETES
# the whole double-quote lookalike family and every zero-width and control codepoint.
# So a perfectly faithful quote of what the model saw must still be locatable in the raw
# page - and it was not, because norm_quote MAPPED those characters where webtext
# DELETES them. On any page carrying quotation marks, which is most research prose, a
# faithful quote scored `not-found` at fraction 0.0. The check was accusing the
# extractor of the engine's own transformation.
for _label, _raw in [
    ("curly quotes",   'The authors said \u201cproductivity rose sharply\u201d in the second year of trials'),
    ("straight quotes",'The authors said "productivity rose sharply" in the second year of trials'),
    ("soft hyphen",    'The authors said produc\u00adtivity rose sharply in the second year of trials'),
    ("zero-width",     'The authors said produc\u200btivity rose sharply in the second year of trials'),
    ("bom + bidi",     'The authors\ufeff said productivity rose\u200e sharply in the second year here'),
]:
    _seen = dr.webtext(_raw)          # exactly what reaches the model
    _res = dr.quote_span(_raw, _seen)  # a perfectly faithful quote of it
    ok(_res["status"] == "located" and _res["foundFraction"] == 1.0,
       "%s: a faithful quote of what the model was SHOWN is located in the raw page "
       "(got %s)" % (_label, _res["status"]))

# PDF line-break hyphenation. The reader collapses the newline to a space before this
# sees it, so the real shape is "con- clusive", not "con-\nclusive". Measured
# 2026-09-08: four published quotes carrying "con- clusive", "standard- ized" and
# "fol- lowing" each scored a false `partial`, and fixing it moved the on-page rate on
# that run's own quotes from 78.3% to 87.0% with no other change.
ok(dr.norm_quote("are not fully con- clusive. Whilst") == "are not fully conclusive. whilst",
   "a word split across a PDF line break is rejoined")
ok(dr.norm_quote("the result - which was good") == "the result - which was good",
   "a real dash is NOT welded shut: it carries a space before the hyphen too")
ok(dr.quote_span("studies are not fully conclusive whilst some have shown otherwise here",
                 "studies are not fully con- clusive whilst some have shown otherwise here"
                 )["status"] == "located",
   "so a faithful quote from a hyphenated PDF is located, not accused")

# THE regression that matters. Measured 2026-09-08: an exact-match-or-nothing scorer
# called a PMC quote `not-found` at fraction 0.0 while the quote was on the page in
# full - a manufactured fabrication signal, the worst thing this check could do.
_tail = "productivity rose 13 percent over six months, and the effect persisted through the follow-up peroid"
_r = dr.quote_span(_PAGE, _tail)
ok(_r["status"] == "located-approx" and _r["foundFraction"] >= 0.9,
   "one wrong character in the tail does NOT collapse the verdict to not-found: a "
   "scorer that strict manufactures the fabrication signal it exists to detect")
_stitch = dr.quote_span(_PAGE, "productivity rose 13 percent over six months, and the "
                               "effect persisted through the follow-up while profits tripled "
                               "worldwide and headcount doubled in every single region")
ok(_stitch["status"] == "partial" and 0.3 < _stitch["foundFraction"] < 0.9,
   "a quote half on the page and half invented reads partial, with the fraction: %s"
   % _stitch["foundFraction"])
ok(dr.quote_span(_PAGE, "productivity soared and every worker was happier than before ever")["status"]
   == "not-found", "a quote that is simply not there reads not-found")
ok(dr.quote_span("", "a quote long enough to clear the floor easily")["status"] == "unverifiable"
   and dr.quote_span(_PAGE, "Cited by: 246")["status"] == "unverifiable",
   "an empty page and a too-short quote are UNVERIFIABLE, never fabrication - a blocked "
   "publisher must not look like a lying extractor")
ok(dr.quote_span(_PAGE, "productivity rose 13 percent over six months")["offset"] is not None,
   "a located quote carries where on the page it sits")

print("\n-- the panel is told the answer, not given an impossible task --")
_lens_src = dr.LENSES[0][2]
ok("paraphrase rather than verbatim page text" not in _lens_src,
   "the support lens no longer asks for a check it cannot perform: it is never shown "
   "the page, so it could not judge whether a quote was verbatim")
ok("already been decided in code" in _lens_src,
   "it is told the result instead, and told to weigh it")
_c = {"claim": "c", "sourceUrl": "u", "quote": "q",
      "quoteCheck": {"status": "located", "foundFraction": 1.0}}
ok("YES" in dr._quote_line(_c), "a located quote is stated as located")
_c["quoteCheck"] = {"status": "partial", "foundFraction": 0.6, "why": "w"}
ok("PARTLY" in dr._quote_line(_c) and "60%" in dr._quote_line(_c)
   and "genuine page text" in dr._quote_line(_c),
   "a partly-located quote states the fraction and says the located part IS real - "
   "most partials are a genuine prefix with a diverging tail, not a fabrication")
_c["quoteCheck"] = {"status": "not-found", "foundFraction": 0.05, "why": "w"}
ok("NOT on the page" in dr._quote_line(_c),
   "only a genuinely absent quote is reported as absent")
_c["quoteCheck"] = {"status": "unverifiable", "foundFraction": None, "why": "blocked"}
ok("not evidence either way" in dr._quote_line(_c),
   "an unverifiable quote is explicitly NOT reported to the panel as a fabrication")
ok("Quote NOT checkable" in dr.p_verify("q", _c, *dr.LENSES[0], 0, 3),
   "and the line actually reaches the verify prompt")
ok(dr._quote_line({"claim": "c"}) == "",
   "a claim with no check adds nothing to the prompt rather than a misleading default")

print("\n-- locatedQuote stops being a silent discard --")
_fb = {("c", "u"): {"claim": "c", "url": "u", "support": "partial", "reasoning": "r",
                    "locatedQuote": "the page said this",
                    "locatedQuoteCheck": {"status": "located"}}}
_rows = dr.citation_rows(_fb)
ok(_rows[0]["locatedQuote"] == "the page said this"
   and _rows[0]["locatedQuoteOnPage"] == "located",
   "the auditor's own verbatim pull is published, with whether it is on the page. It "
   "was demanded on every audit call and read by nothing.")
# Effect, not source-count: the three inline copies had already drifted, with
# `reasoning` present on the happy path and missing from both failure exits. Assert
# the exits agree on the row shape instead of counting call sites.
_k_happy = sorted((r.get("citationDetail") or [{}])[0].keys())
_k_nosyn = sorted((r11.get("citationDetail") or [{}])[0].keys())
ok(_k_happy == _k_nosyn and "locatedQuote" in _k_happy and "reasoning" in _k_nosyn,
   "every report exit builds citation rows with the SAME keys: %s" % ", ".join(_k_happy))

print("\n-- an <item>-wrapped array is data, not a decline --")
ok(dr.as_list('\n<item>first</item>\n<item>second</item>', "t") == ["first", "second"],
   "the structured-output path leaks <item> markup around array elements; every element "
   "is intact, so it is recovered rather than discarded")
ok(dr.as_list("<item>a<item>b", "t") == ["a", "b"],
   "and recovered when the closing tags are absent too")
# The tag NAME varies - it is the singular of the field being filled. Watched live
# 2026-09-08: a framing call returned `\n<hypothesis>\n<hypothesis>Output is...`, so
# matching the literal string "<item>" had fixed exactly one symptom of the leak.
ok(dr.as_list("\n<hypothesis>\n<hypothesis>Output is sustained</hypothesis>"
              "\n<hypothesis>It is not</hypothesis>", "t")
   == ["Output is sustained", "It is not"],
   "any tag the string opens with is recovered, not just <item>, and a repeated "
   "opening tag does not produce an empty leading element")
# The leaked markup NESTS. Watched live 2026-09-08: framing returned <item> wrapping
# <hypothesis>, and trimming only the edge characters left `hypothesis>...</hypothesis`
# welded to the text. The corrective retry then told the model to "keep the wording you
# already wrote" while showing it mangled wording - and the very next attempt returned
# the same broken shape, so the informed re-ask bought nothing.
ok(dr.as_list("\n<item>\n<hypothesis>Strong Ericsson claim: practice is the primary "
              "driver</hypothesis>\n</item>\n<item>\n<hypothesis>The effect is overstated "
              "once controls are added</hypothesis>\n</item>", "t")
   == ["Strong Ericsson claim: practice is the primary driver",
       "The effect is overstated once controls are added"],
   "a nested tag is stripped from the recovered text, so the retry is shown the wording "
   "the model actually wrote rather than a fragment of markup")
ok(dr.as_list("the result was < 5 percent overall", "t") == [],
   "a stray angle bracket in prose is still not a list - the match is anchored at the "
   "start, which is what markup leakage looks like and prose does not")
ok(dr.as_list("just a sentence", "t") == []
   and dr.as_list("a <item> in prose", "t") == [],
   "a plain string is still rejected, and a tag appearing MID-sentence no longer "
   "triggers recovery either: anchoring the match tightened this, because markup "
   "leakage always opens the string. The 226-one-character-claims bug must not return.")
ok(dr.as_list(["already", "a", "list"], "t") == ["already", "a", "list"],
   "a real array is untouched")
# Costed, not cosmetic: the corrective retry re-asks the SAME question, so a
# deterministic shape leak used to consume the whole retry budget and could fail the
# framing call outright - the first call of the run.
ok("<item>" in open(dr.__file__, encoding="utf-8").read(),
   "the recovery lives at the seam, so every array field in every schema gets it")

ok("25%" in dr._evidence_base([{"tier": "T2", "claims": 1}])["verdict"],
   "a thin verdict says what a thin run has actually scored, not just that it is thin")

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
    "assumptions": [], "whatWouldChangeTheAnswer": [], "hypotheses": [], "needsGeneralWeb": True})
ok(len(_short) == 3, "an empty framing contract is caught on all three required arrays, not accepted")
ok(any("hypotheses=0" in x for x in _short), "and the log names which array and by how much: %r" % _short[:1])
ok(dr._schema_shortfall(dr.S_FRAMING, {
    "decisionAtStake": "x", "keyQuestion": "y",
    "assumptions": ["a", "b"], "whatWouldChangeTheAnswer": ["c", "d"],
    "hypotheses": [{"hypothesis": "h1", "killCriterion": "k1"},
                   {"hypothesis": "h2", "killCriterion": "k2"}],
    "needsGeneralWeb": False}) == [],
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
# CALLED, not merely `callable`. Renaming engine.TIERS to DEPTH_BUDGETS left
# probes.py reading the old name at two sites, so run_critic_probes raised
# AttributeError at HEAD - this repo's only ground-truth instrument, dead, under a green
# suite and seven green CI jobs, because the assertion here was `callable(...)`. A name
# that exists is not a function that runs, which is the same lesson as a marker that
# exists not being a feature that works.
_probe_rep = {"depth": "quick", "question": "Does X cause Y?",
              "summary": "A summary sentence.",
              "findings": [{"claim": "f1", "confidence": "high", "sources": ["https://a.org/1"]}],
              "sources": [{"url": "https://a.org/1", "tier": "T2", "claims": 1}],
              "citationDetail": [{"claim": "f1", "url": "https://a.org/1", "support": "supported"}],
              "scopeContract": {"keyQuestion": "k", "provenance": {"keyQuestion": "supplied"}},
              "coverage": [{"subQuestion": "s1", "status": "partial"}]}
for _probe in (P.run_audit_probes, P.run_critic_probes, P.run_framing_probes):
    try:
        _res = _probe(_probe_rep)
        _ran = isinstance(_res, dict)
    except Exception as _e:                      # noqa: BLE001 - a probe that raises IS the failure
        _ran, _res = False, "%s: %s" % (type(_e).__name__, _e)
    ok(_ran, "%s RUNS against a finished report, not just imports: %s"
             % (_probe.__name__, "ok" if _ran else _res))
ok(callable(P.main), "and the runner is there, so #10 and #11 can be re-measured")
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

ok(("no usable JSON in the reply" in _agent_src) and "exhausted" in _agent_src,
   "every way agent() can return None now logs a reason: one run reported 'synthesis "
   "failed' with nothing anywhere in the log saying why")

_fallback = _engine_txt.split("Synthesis failed - returning", 1)[1].split("\n\n", 1)[0]
ok("calibration=calibration" in _fallback and "droppedSample=dropped_sample" in _fallback,
   "a failed synthesis no longer discards the calibration and the dropped-claim sample: "
   "one run computed kappa=0.7115 at n=30, logged `calibrated`, and then threw it away")
ok("synthesisFailed" in _fallback,
   "and the report says it is incomplete rather than empty, naming what DID run")

print("\n-- PDFs are read as text, never passed on as binary --")
import zlib as _zlib
from deepresearch import search as _S
def _mkpdf(runs):
    """A minimal one-page PDF whose content stream is FlateDecode'd, like a real one."""
    body = b"BT /F1 12 Tf " + b" ".join(runs) + b" ET"
    comp = _zlib.compress(body)
    # Built by concatenation, not %-formatting: the literal "%PDF" header contains "%P",
    # which bytes-% reads as a format spec and raises.
    return (b"%PDF-1.5\n1 0 obj\n<< /Length " + str(len(comp)).encode()
            + b" /Filter /FlateDecode >>\nstream\n" + comp
            + b"\nendstream\nendobj\ntrailer\n<< >>\n%EOF")
_kerned = _mkpdf([b"[(Employment)-250(Effects)-250(of)-250(Minimum)-250(Wages)]TJ",
                  b"[(in)-250(New)-250(Jersey)-250(and)-250(Pennsylvania)]TJ"])
_txt = _S.pdf_text(_kerned)
ok("Employment Effects of Minimum Wages" in _txt,
   "kerning is read as word breaks: a TJ array separates runs by thousandths of an em, and "
   "naive concatenation gave 'EmploymentEffectsofMinimumWages'")
ok("New Jersey and Pennsylvania" in _txt, "across multiple text operators too")
ok(_S.pdf_text(_mkpdf([b"(hello) Tj"])).strip() == "hello", "a plain Tj string is read")
ok(_S.pdf_text(b"not a pdf at all") == "", "a non-PDF yields nothing rather than raising")
_esc = _S.pdf_text(_mkpdf([rb"[(a\(b\)c)]TJ"]))
ok("a(b)c" in _esc, "escaped parentheses survive")
_src = open(_S.__file__, encoding="utf-8").read()
ok('raw[:5] == b"%PDF-"' in _src and '"via": "pdf-unreadable"' in _src,
   "fetch() detects a PDF by its magic bytes and REFUSES when extraction is too thin - "
   "an unreadable PDF is unreachable, which the auditor understands; binary looked like "
   "a page that merely disagreed")
ok('def _get_bytes' in _src and "_readable(_decode(raw))" in _src,
   "fetch reads BYTES first: the old latin-1 fallback decoded a PDF into mojibake that "
   "every caller downstream treated as page text")

_eng = open(dr.__file__, encoding="utf-8").read()
_engine_src = _eng
_js = open(os.path.join(ROOT_DIR, 'integrations/claude-code/deepresearch.js'), encoding='utf-8').read() if 'ROOT_DIR' in dir() else open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'integrations/claude-code/deepresearch.js'), encoding='utf-8').read()

# Exercise the real web_fetch against a stubbed _search.fetch, rather than asserting a
# source substring. The substring version passed for months and then failed the moment a
# variable was renamed, which is the wrong signal in both directions: it never checked
# that `via` was recorded, only that a line of code looked a certain way.
_real_fetch, _calls = dr._search.fetch, []
try:
    def _stub_fetch(u, cap=14000):
        _calls.append((u, cap))
        return ("body of " + u)[:cap], {"via": "crossref-api", "doi": "10.1/x"}
    dr._search.fetch = _stub_fetch
    dr._page_cache.clear(); dr._fetch_meta.clear()
    dr._page_tally.update({"hits": 0, "misses": 0, "charsServedFromCache": 0})
    _t1 = _REAL_WEB_FETCH("https://p.org/a", cap=500)
    ok(dr._fetch_meta.get("https://p.org/a", {}).get("via") == "crossref-api",
       "every source row records HOW it was read, so a paper and an abstract stub are no "
       "longer indistinguishable in the report")
    _t2 = _REAL_WEB_FETCH("https://p.org/a", cap=500)
    ok(_t2 == _t1 and len(_calls) == 1 and dr._page_tally["hits"] == 1,
       "the same page is fetched once per run: the audit re-reads pages the sweep already "
       "pulled, 18 of 30 times in each of two recorded runs")
    _REAL_WEB_FETCH("https://p.org/a", cap=9000)
    ok(len(_calls) == 2,
       "a cache entry read at a smaller cap does NOT serve a larger one - it refetches, "
       "rather than silently handing back a truncated page")
    def _empty_fetch(u, cap=14000):
        _calls.append((u, cap)); return "", {"via": "failed"}
    dr._search.fetch = _empty_fetch
    _REAL_WEB_FETCH("https://dead.org/x"); _REAL_WEB_FETCH("https://dead.org/x")
    ok(len([c for c in _calls if c[0] == "https://dead.org/x"]) == 2,
       "an empty fetch is never cached: one transient failure must not delete a source "
       "for the rest of the run")
finally:
    dr._search.fetch = _real_fetch
    dr._page_cache.clear(); dr._fetch_meta.clear()
    dr._page_tally.update({"hits": 0, "misses": 0, "charsServedFromCache": 0})

print("\n-- token accounting cannot go silently incomplete again --")
_u = {"in_tok": 0, "out_tok": 0, "cache_write_tok": 0, "cache_read_tok": 0, "usageUnrecorded": {}}
dr._record_usage({"input_tokens": 100, "output_tokens": 20,
                  "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 300}, into=_u)
ok(_u["cache_write_tok"] == 3000 and _u["cache_read_tok"] == 300,
   "cache tokens are counted: recording only input+output made a cached run's totals "
   "wrong by exactly the amount the cache handled, and it read as zero either way")
dr._record_usage({"output_tokens_details": {"thinking_tokens": 77},
                  "some_future_field": 5, "service_tier": "standard", "flagged": True}, into=_u)
ok(_u["usageUnrecorded"].get("output_tokens_details.thinking_tokens") == 77,
   "a nested token field is censused, not dropped - thinking tokens live one level down")
ok(_u["usageUnrecorded"].get("some_future_field") == 5,
   "a usage field this build has never heard of is still counted, under its own name: "
   "the accounting says what it missed instead of quietly under-reporting")
ok("service_tier" not in _u["usageUnrecorded"] and "flagged" not in _u["usageUnrecorded"],
   "non-numeric and boolean usage fields are not counted as tokens")

print("\n-- prompt caching is refused, and the reasons stay checkable (ADR-0003) --")
_fp = dr.p_fact("the claim", "https://x.org/p", "P" * 12000)
ok(_fp.index("## Statement") < _fp.index("## Page content"),
   "the audit states the claim BEFORE the page. Caching needs the page first, and that "
   "reorder moved 6 of 30 verdicts against a 0-of-30 self-disagreement control")
ok("cache_control" not in open(dr.__file__, encoding="utf-8").read(),
   "no prompt block is marked for caching anywhere")
ok(len(dr.CC_SYSTEM_PREFIX) // 4 < 1024,
   "the system block is far UNDER that minimum (47 tokens), which is why it is not "
   "marked for caching: the marker would cache nothing and bill a 25% write surcharge")
_lens = dr.p_verify("q", {"claim": "c", "sourceUrl": "u", "quote": "z"},
                    *dr.LENSES[0], 0, 3)
ok(len(_lens) // 4 < 1024,
   "an ENTIRE verify prompt is ~350 tokens, also under the floor - caching the lens "
   "boilerplate, as suggested, would have cached nothing at all")
ok("fetchVia=_via_census" in _eng and "abstractOnlySources" in _eng,
   "and the run censuses it, with an honest limit explaining what crossref-fallback means")

print("\n-- results that are not about the question are junk, not evidence --")
_junk = [{"url": "https://cebupacificair.com/%d" % i, "title": "Cebu Pacific booking",
          "snippet": "book flights"} for i in range(8)]
_good = [{"url": "https://x.org/a", "title": "Minimum wage employment effects in New Jersey",
          "snippet": "Card and Krueger"}]
try:
    _S.relevant(_junk, "Card Krueger minimum wage New Jersey employment"); _caught = ""
except RuntimeError as e:
    _caught = str(e)
ok("unrelated to the query" in _caught,
   "a full page of results about an airline is REFUSED for a minimum-wage query - measured "
   "live, and searchHealth read ok=23 results=154 the whole time")
ok(_S.relevant(_good, "minimum wage employment") == _good, "a related result is kept")
ok(len(_S.relevant(_good + _junk[:1], "minimum wage employment")) == 1,
   "and the junk beside it is dropped without failing the whole query")
try:
    _S.relevant(_good + _junk, "minimum wage employment"); _floor = ""
except RuntimeError as e:
    _floor = str(e)
ok("topically related" in _floor,
   "below the floor the backend is treated as failed, so the chain falls through instead "
   "of passing a page that is 1/9 relevant")
ok(_S.relevant(_junk, "") == _junk, "an empty query cannot be judged, so nothing is dropped")
_ssrc = open(_S.__file__, encoding="utf-8").read()
ok("one host owning the" in _ssrc and "serving junk" in _ssrc,
   "and one host owning almost every result is refused too - a different tell for the "
   "same failure")
_esrc = open(dr.__file__, encoding="utf-8").read()
ok("_pick_tally" in _esrc and "pickStarvation" in _esrc and "rejected EVERY hit" in _esrc,
   "the run also counts how often the picker was handed hits and chose none - the only "
   "in-pipeline symptom this had, and it looked exactly like a fussy model")
ok("irrelevantSearchResults" in _esrc,
   "and honestLimits explains that searchHealth counts results, not relevance")

print("\n-- a blocked publisher still yields its abstract --")
ok(_S.doi_in_url("https://www.pnas.org/doi/10.1073/pnas.2200300119") == "10.1073/pnas.2200300119",
   "a DOI is found in a publisher's own path, not just in a doi.org link")
ok(_S.doi_in_url("https://dl.acm.org/doi/pdf/10.1145/3757892.3757904") == "10.1145/3757892.3757904",
   "and the /pdf segment does not corrupt it")
ok(_S.doi_in_url("https://www.bloomberg.com/news/articles/2024-01-01") is None,
   "a URL with no DOI gets no fallback - the run still records a real failure")
ok('"via": "crossref-fallback"' in _src and '"abstractOnly": True' in _src,
   "the fallback labels itself an abstract, so the auditor is not judging a claim against "
   "a stub while believing it read the paper")

print("\n-- survivor-only citation accuracy travels alongside the pool number --")
ok('"citationAccuracySurvivorsOnly"' in _engine_txt and '"survivorsOnlyNote"' in _engine_txt,
   "the report now carries the market-comparable number (panel survivors only) "
   "beside the harsher one this project leads with (the full verification pool, "
   "killed claims included) - so a stricter self-measurement never accidentally "
   "under-sells a real comparison")

print("\n-- catchRateStrict: partial no longer scores as a caught defect --")
_probe_results = [
    {"probe": "negated", "claim": "x", "support": "unsupported"},
    {"probe": "inflated-number", "claim": "x", "support": "partial"},
    {"probe": "fabricated-specificity", "claim": "x", "support": "partial"},
    {"probe": "scope-inflation", "claim": "x", "support": "partial"},
    {"probe": "unsupported-causation", "claim": "x", "support": "supported"},
]
_scored = P.score_audit_probes(_probe_results)
ok(_scored["catchRateStrict"] == 0.2,
   "1 of 5 unsupported -> catchRateStrict=0.2, not the lenient 0.8 that counted 3 "
   "partials as caught - measured live: an inflated-number probe (a real figure x10) "
   "scored partial, which the OLD headline metric called a catch")
ok(_scored["catchRate"] == 0.8, "the lenient number still exists as a labelled secondary")
ok("catchRateNote" in _scored and "NOT caught" in _scored["catchRateNote"],
   "and the report says plainly which one is honest")
ok("below 0.8" in _scored["reading"], "the reading text now keys off the strict rate")

print("\n-- selftest retries a general-web backend before declaring it dead --")
_sel_src = _insp.getsource(dr.selftest)
ok("all_backends=True" in _sel_src and "for attempt in range(2)" in _sel_src,
   "measured live: selftest declared ddg-html dead off ONE probe, and the real run 20 "
   "minutes later pulled 40 results from it across 72 attempts - one rate-limit "
   "challenge is not the same as a dead backend")
# Signature check, not source text: it broke the moment a parameter was added, which is
# the wrong signal. What matters is that both knobs are reachable.
import inspect as _insp   # noqa: E402
ok(set(["all_backends", "junk_filter"]).issubset(
       _insp.signature(_REAL_WEB_SEARCH).parameters),
   "web_search exposes all_backends, so a retry is not skipped by an earlier backend "
   "already satisfying n, AND junk_filter, so the counter-evidence lens can opt out of a "
   "shared-word filter that would drop the contradiction it went looking for")

print("\n-- the degraded-mode searxng remedy says what answers FROM HERE, not one address --")
# Measured 2026-09-16 inside the messenger deployment: the DEGRADED hint told the agent
# to export 127.0.0.1:8888 - the host-side publish - but from inside the container the
# same instance answers only as searxng:8080, so the remedy followed verbatim fixed
# nothing. The hint must probe candidates from the vantage the failure happened in.
ok("probe_searxng" in _sel_src and "127.0.0.1:8888" in _sel_src and "searxng:8080" in _sel_src,
   "the selftest's degraded hint probes BOTH compose addresses (host publish and docker "
   "network name) via the search module's prober instead of prescribing one")
import http.server as _hs, socket as _sock, threading as _thr  # noqa: E402

class _ProbeJSON(_hs.BaseHTTPRequestHandler):
    body = b'{"results": [{"url": "https://example.com/a"}, {"url": "https://example.com/b"}]}'
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)
    def log_message(self, *a):
        pass

class _ProbeEmpty(_ProbeJSON):
    body = b'{"results": []}'

def _serve(cls):
    srv = _hs.ThreadingHTTPServer(("127.0.0.1", 0), cls)
    _thr.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

_srv_full, _srv_empty = _serve(_ProbeJSON), _serve(_ProbeEmpty)
ok(searchmod.probe_searxng("http://127.0.0.1:%d" % _srv_full.server_address[1]) == 2,
   "a live searxng JSON endpoint reports its result count")
ok(searchmod.probe_searxng("http://127.0.0.1:%d" % _srv_empty.server_address[1]) == 0,
   "reachable-but-empty reads as 0, not None - suspended upstream engines are a "
   "different failure from a wrong address, and the hint must not conflate them")
_srv_full.shutdown(); _srv_empty.shutdown()
_sk = _sock.socket(); _sk.bind(("127.0.0.1", 0)); _dead = _sk.getsockname()[1]; _sk.close()
ok(searchmod.probe_searxng("http://127.0.0.1:%d" % _dead) is None,
   "an address with nothing behind it reads as None - that is the 'wrong vantage' signal "
   "the degraded hint prints next to each candidate")

print("\n-- every report exit carries the instruments, not just the happy path --")
# Architecture review, 2026-09-07: I had reported this fixed. It was fixed on ONE of
# four exits. Verify by counting every `return dict(base` site in the source rather
# than by driving each exit live - some (all-refuted, all-demoted-by-audit) need a
# specific model-response sequence to reach and are already covered end to end by the
# happy-path tests; what was actually missing was the KEYWORD ARGUMENT, and that is
# what this checks.
import inspect as _insp2
_eng_src_full = _insp2.getsource(dr)
_exits = [i for i in range(len(_eng_src_full)) if _eng_src_full.startswith("return dict(base", i)]
ok(len(_exits) == 4, "still four report-assembly exits (not_ranked, all_refuted, "
                     "all_demoted, happy) - a fifth would need this test extended")
_carries = [(("honestLimits" in _eng_src_full[i:i + 1100]),
            ("calibration=calibration" in _eng_src_full[i:i + 1100]),
            ("droppedSample=dropped_sample" in _eng_src_full[i:i + 1100]))
           for i in _exits]
ok(all(hl for hl, _, _ in _carries),
   "ALL FOUR exits carry honestLimits now - previously 2 of 4 did, including the "
   "all-refuted exit where killRateMeans is most load-bearing")
ok(sum(1 for _, cal, drop in _carries if cal and drop) == 3,
   "the three exits reached AFTER calibration/droppedSample are computed all carry "
   "them; only the not-ranked exit (before verification even starts) correctly omits "
   "them, because they do not exist yet")
ok("def _honest_limits(" in _eng_src_full,
   "honestLimits is a single shared function now, not five hand-copied dict literals")

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
_full = dict(_sup, hypotheses=[{"hypothesis": "h1", "killCriterion": "k1"}, {"hypothesis": "h2", "killCriterion": "k2"}],
             needsGeneralWeb=True)
_r2 = run(contract=_full)
ok(any("nothing to draft" in l for l in LOGS) and not any(l.strip().startswith("[framing]") for l in LOGS),
   "a FULLY supplied contract skips the framing call entirely - no model call for a decision already made")
ok(all(v == "supplied" for v in _r2["scopeContract"]["provenance"].values()), "and every field reads supplied")
_r3 = run()
ok(all(v == "drafted" for v in _r3["scopeContract"]["provenance"].values()),
   "no contract supplied: every field is drafted, and the report SAYS so rather than looking identical")
# EFFECT, not presence. The previous test here asserted the provenance string was IN the
# prompt and passed for a full day while the instruction was being ignored: the note
# rendered under check 2, and check 3 then re-issued the very phrase it forbade. Assert
# what the prompt DOES - whether the forbidden instruction is there at all.
_FORBIDDEN = "a premise accepted instead of tested"
_crit = lambda prov: dr.p_critic(0, 2, "Q?", ["s1"], [], [{"claim": "c"}], "S.", [], prov)
_all_sup = {f: "supplied" for f in dr.FRAMING_FIELDS}
ok(_FORBIDDEN not in _crit(_all_sup),
   "with every field ratified there is NO instruction to hunt an untested premise - the "
   "caveat-plus-instruction shape let the instruction win")
ok(_FORBIDDEN in _crit({f: "drafted" for f in dr.FRAMING_FIELDS}),
   "with every field drafted the hunt instruction is present in full")
ok(_FORBIDDEN in _crit(None), "and with no provenance at all the check is unchanged")
_mixed = _crit(dict(_all_sup, hypotheses="drafted"))
_after = _mixed[_mixed.index("RATIFIED"):]
ok(_FORBIDDEN in _after.split("DRAFTED hypotheses", 1)[1],
   "on a mixed contract the hunt is scoped to the DRAFTED fields, stated after them")
ok(_FORBIDDEN not in _mixed.split("RATIFIED", 1)[1].split("- The model DRAFTED", 1)[0],
   "and never appears in the ratified half")
ok("do not report them as untested" in _mixed and "3. **Plan flaws" in _mixed,
   "the rule lives INSIDE check 3, not orphaned under check 2 where it used to render")
ok("RATIFIED" not in _crit(None), "says nothing about ratification when there is none")

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
# shape() drops a malformed ITEM inside an array - right for model output, wrong for a file
# a person wrote. Found on a live test: 3 hypotheses, one missing killCriterion, ACCEPTED
# with 2 because the survivors still met minItems, and the third vanished with a log line.
_e = _raises({"hypotheses": [{"hypothesis": "h1", "killCriterion": "k1"},
                             {"hypothesis": "h2", "killCriterion": "k2"},
                             {"hypothesis": "h3 the human wrote, no kill criterion"}]})
ok(_e and "3 item(s) and 2 survived" in _e,
   "a supplied item is never DROPPED even when the survivors still satisfy minItems - "
   "that would be a silent discard of something a person wrote")
ok(dr.load_contract(_write({"assumptions": ["a", "b"]})) == {"assumptions": ["a", "b"]},
   "and an array whose items all survive is untouched")
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
    "assumptions": [], "whatWouldChangeTheAnswer": [], "hypotheses": [], "needsGeneralWeb": True}),
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

print("\n-- every gate proves a good and a bad reference, before any API call --")
# A gate that cannot fail is indistinguishable from no gate, and this project has shipped
# that shape more than once: parity markers passing on a comment, catchRate counting a
# partial as a catch, challenge markers unreachable for the input they were added for.
import json as _json2   # noqa: E402
from deepresearch import instruments as _inst   # noqa: E402
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ok(_inst.verify() == [],
   "every reference in contract/conformance.json answers correctly in this build")
_ni, _ng, _nc = _inst.counts()
ok(_ng >= 9 and _nc >= 45,
   "and the contract covers %d instruments, %d of them gates, over %d references" % (_ni, _ng, _nc))

_doc = _json2.load(open(os.path.join(_ROOT, "contract", "conformance.json"), encoding="utf-8"))
_gate_names = [f for f, k in _doc["instruments"].items() if k == "gate"]
ok(len(_gate_names) == _ng, "the gate count comes from the contract, not from a number typed here")

# The structural rule, checked by breaking it. A gate with no bad reference, and a gate
# whose bad reference answers exactly what its good ones answer, must BOTH be caught -
# the second is the one that bites, because a gate can have many cases and still never
# have been observed to reject anything.
_no_bad = _json2.loads(_json2.dumps(_doc))
_no_bad["cases"]["host_ambiguous"] = [c for c in _no_bad["cases"]["host_ambiguous"]
                                      if c.get("ref") != "bad"]
ok(any("no `bad` reference" in f for f in _inst.check_structure(_no_bad)),
   "a gate with no bad reference is caught: nothing shows it can reject at all")

_toothless = _json2.loads(_json2.dumps(_doc))
for _c in _toothless["cases"]["host_ambiguous"]:
    if _c.get("ref") == "bad":
        _c["out"] = False
        _c.pop("out_by_runtime", None)
ok(any("never been observed to reject" in f for f in _inst.check_structure(_toothless)),
   "and so is a gate whose bad references answer exactly what its good ones answer - "
   "having cases is not the same as having been shown to reject something")

_undeclared = _json2.loads(_json2.dumps(_doc))
_undeclared["instruments"]["never_bound"] = "gate"
ok(any("never_bound" in f for f in _inst.check_structure(_undeclared)),
   "an instrument declared with no cases is caught too, so the contract cannot claim "
   "coverage it does not have")

ok(dr.EXIT_CONTRACT == 4,
   "and a build whose gates are broken exits CONTRACT (4) rather than producing a report "
   "nobody can check - verified by hand against a real run, which refused to start")

print("\n-- depth budgets are contract data, not two literals --")
# The tier RULES were moved to contract/tiers.json after researchgate.net graded T4 in
# Python and T3 in JS. The BUDGETS were left behind and drifted the same way one file
# over: `quick` verified 10 claims here and 14 in the JS build - 30 agent calls against
# 42 for the same requested depth, declared nowhere.
_DEPTHS = _json2.load(open(os.path.join(_ROOT, "contract", "depths.json"), encoding="utf-8"))
ok(dr.DEPTH_BUDGETS == _DEPTHS["depths"],
   "the engine's depth table IS the contract file, not a copy of it - a copy is what "
   "drifted")
ok(dr.DEPTH_BUDGETS["quick"]["max_verify"] == 10,
   "quick verifies 10 claims. Every recorded run and every calibration number in runs/ "
   "came from this engine at 10, so adopting the JS build's 14 would have silently "
   "changed what the historical quick numbers mean")
for _d, _cfg in dr.DEPTH_BUDGETS.items():
    ok(_cfg["lenses"] == 3,
       "%s runs all 3 lenses: 2 of N must refute to kill, so at 2 lenses a 1-1 split "
       "survives and no single lens can ever kill anything" % _d)
_sys_path_added = os.path.join(_ROOT, "tools")
if _sys_path_added not in sys.path:
    sys.path.insert(0, _sys_path_added)
import sync_tiers as _st   # noqa: E402
_js_block = _st.render_depths(_DEPTHS)
ok(_st.render_depths(_DEPTHS) in open(
       os.path.join(_ROOT, "integrations", "claude-code", "deepresearch.js"), encoding="utf-8").read(),
   "and the JS build's table is GENERATED from that same file, byte-for-byte - the "
   "parity test checks this too, so neither copy can be edited by hand")
ok("maxVerify: 10" in _js_block and "deepenRounds" in _js_block and "factAudit" in _js_block,
   "the generator owns the one thing that genuinely differs between the runtimes: the "
   "key names. The numbers cannot differ because there is only one set")

print("\n-- a negation difference is caught in BOTH directions and BOTH paths --")
# v1.10.1 made this one-directional to stop a "false accusation": a faithful positive
# rewording of a registered null being marked post-hoc. That had the costs backwards. The
# accusation cost only the LABEL - the verdict still stamped true via the text path at
# 0.933 - while the open direction cost the STAMP, because deleting a registered negation
# keeps every content word and scores 1.000 (`not` is a stopword, `do` is two characters).
_V10_NULL = ("No meaningful difference: under matched calorie deficits, IF and CCR produce "
             "statistically similar fat loss, and the difference is adherence, not "
             "metabolic superiority")
_V10_RW = ("H1: Under matched calorie deficits, IF and CCR produce statistically similar fat "
           "loss; the difference is adherence rather than metabolic superiority")
_MWR = "Minimum wage increases reduce teen employment"
_MWN = "Minimum wage increases do not reduce teen employment"
ok(dr._hyp_mismatch(dr._hyp_key(_MWR), dr._hyp_key(_MWN)),
   "THE MIRROR: a verdict that DELETES the registered negation is caught - identical token "
   "sets, overlap 1.000, so a registered hypothesis could be adjudicated as its exact "
   "opposite and stamped a prediction that survived")
ok(dr._hyp_mismatch(dr._hyp_key("The intervention has an effect on employment"),
                    dr._hyp_key("The intervention has no effect on employment")),
   "and the same flip from a registered NULL, which is the flattering direction")
for _neg in (_MWN, "Minimum wage increases have no effect on teen employment"):
    ok(dr._hyp_mismatch(dr._hyp_key(_neg), dr._hyp_key(_MWR)),
       "while a verdict that ADDS a negation is still caught: %r" % _neg[24:52])
ok(not dr._same_hypothesis(dr._hyp_key(_MWR), dr._hyp_key(_MWN)),
   "the TEXT path checks it too - fixing only the number path closed nothing, because "
   "this stamped true there instead by the same 1.000 overlap")
ok(dr._negation_differs("does not reduce employment", "reduces employment")
   and not dr._negation_differs("reduces employment", "no meaningful difference")
   and not dr._negation_differs("the groups perform the same on memory tasks",
                                "the groups show no difference in memory performance"),
   "the check is DIRECTION-aware by construction: ADD fires, DROP fires only on "
   "near-identity, and a faithful rewording that drops the negation while genuinely "
   "rewording does not fire. The terse DROP pair here is the named residual - on "
   "17-24 character strings the ratio compresses below any bar, so the number is "
   "believed, exactly as _hyp_mismatch documents for the token floor")

ok(dr._hyp_mismatch(dr._hyp_key(_V10_RW), dr._hyp_key(_V10_NULL)),
   "and the KNOWN COST is taken knowingly: a positive restatement of a registered null is "
   "marked post-hoc. Only 8 verdict/registered pairs on record carry a number and none "
   "differ in negation, so this chooses between two unobserved failures - and the policy "
   "is that a false 'pre-registered' is the one to prevent, a false 'post-hoc' understates")
ok(not dr._hyp_mismatch(dr._hyp_key("Minimum wage increases raise teen employment"),
                        dr._hyp_key(_MWR)),
   "and the NAMED LIMIT is pinned rather than claimed closed: an antonym flip carries no "
   "negator word, covers 0.833 and passes, which is why the label says 'added negation "
   "checked - NOT polarity'")
ok("added negation checked - NOT " in _ENG,
   "the published label says what is checked, not more")

# The sneakiest instance of the antonym limit: BOTH sides negate, so nothing is added and
# the check correctly does not fire - the flip lives in "unlikely" against "likely". This
# function looks like it should catch it, so the limit is pinned rather than assumed.
ok(not dr._hyp_mismatch(
       dr._hyp_key("Minimum wage increases are not unlikely to reduce teen employment"),
       dr._hyp_key("Minimum wage increases are not likely to reduce teen employment")),
   "a flip INSIDE a shared negation passes at 0.857 - pinned as a named limit, because "
   "the added-negation check looks like it should see this one and does not")
ok(not dr._negation_differs("not unlikely to reduce", "not likely to reduce"),
   "and it is right not to fire: both sides carry a negator, so they do not DIFFER - the "
   "inversion lives in 'unlikely' against 'likely', which is an antonym, not a negation")

print("\n-- the README's #9 table is generated, not typed --")
# It claimed a tool regenerated it so it "cannot drift again". That was true of the
# regime tables and NOT of this one: it listed five samples when eight were archived,
# omitting v3-minwage-fixed (90% vs 67%) and v3-nudge-contract (60% vs 67%), and its
# headline read "four of five" where no stated rule gives four. Both omissions and the
# overstatement run in the flattering direction, in the section whose whole purpose is to
# report an unflattering result.
sys.path.insert(0, os.path.join(_ROOT, "tools"))
import compare_regimes as _cr   # noqa: E402
_readme = open(os.path.join(_ROOT, "README.md"), encoding="utf-8").read()
# NOT vestigial, though a review read it that way: this is the guard that the README
# block matches what the tool emits from runs/, which is a different assertion from the
# derived-conclusion ones below. Archiving a run without regenerating turns this red on
# purpose, and CONTRIBUTING now says how to satisfy it.
ok(_cr.dropped_markdown() in _readme,
   "the README carries exactly what tools/compare_regimes.py --dropped-md emits, so a "
   "new run cannot leave the table behind")
ok(_cr.DROPPED_START in _readme and _cr.DROPPED_END in _readme,
   "and the block is marked generated, so nobody hand-edits it back into drift")
ok(_cr.SAME_WITHIN == 5,
   "the headline tally has a STATED rule - within %d points counts as 'as well as' - "
   "because the previous count could not be derived from any rule" % _cr.SAME_WITHIN)
# The CONCLUSION is derived too. It was fixed prose asserting "the ranking is not
# selecting for verifiability", written when the samples ran one way; a later run came
# back 33% against 100% of kept and the sentence still asserted the old reading over a
# bare majority. A generated table with a hand-written conclusion is half generated, and
# the hand-written half is the one that overstates.
# Driven with COUNTS, not by matching a phrase in whatever runs/ holds today. The
# previous version passed whenever the signal phrase appeared anywhere in the block, and
# archiving a tenth sample would have flipped its subject without touching a line of code.
for _same, _tot, _want in ((9, 9, "not selecting"), (8, 9, "not selecting"),
                           (5, 9, "no consistent signal"), (4, 9, "no consistent signal"),
                           (2, 9, "is selecting for verifiability"),
                           (0, 9, "is selecting for verifiability")):
    ok(_want in _cr.reading_for(_same, _tot),
       "%d of %d reads as %r, so the sentence follows the tally rather than restating a "
       "conclusion the samples no longer support" % (_same, _tot, _want))
ok(_cr.reading_for(0, 0) and (_cr.CLEAR_MINORITY, _cr.CLEAR_MAJORITY) == (0.25, 0.75),
   "the bands are named constants pinned to their VALUES - a review noted the previous "
   "assertion only checked one was smaller than the other, which both could have moved "
   "without failing - and an empty table does not divide by zero")

print("\n-- the coverage line counts sub-questions, not buckets --")
# A live run logged "Verify pool spans 9 distinct sub-question buckets (of 8)" - more
# than the total, because `(unassigned)` is a bucket and was counted as a sub-question.
# Impossible-looking, and wrong in the flattering direction: it overstates how much of
# the checklist the verify pool reaches.
ok(dr.sq_key({"subQuestionIndex": 0}, 4) == "(unassigned)"
   and dr.sq_key({"subQuestionIndex": 9}, 4) == "(unassigned)"
   and dr.sq_key({"subQuestionIndex": 2}, 4) == "sq2",
   "an index outside the checklist lands in (unassigned), which is a bucket and not a "
   "sub-question")
ok("of %d sub-questions" in _ENG and "map to no sub-question" in _ENG,
   "so the log reports assigned coverage and unassigned claims separately, and can never "
   "print a number larger than the checklist")

print("\n-- a mandatory field that points at itself is not an answer --")
# Found by reading a real report, not by a test. 4 of the 20 recorded runs carrying
# `strongestArgumentAgainst` published a cross-reference to the field itself - and the
# live run of 2026-09-15 made it 5 of 21, inventing a sibling key
# `strongestArgumentAgainst_unused` holding "". In none of them does the argument exist
# anywhere else in the report: it is missing, not misfiled. A 24% silent-content rate on
# the one field whose entire job is to argue against the answer.
for _ptr in ("See strongestArgumentAgainst field above (duplicate not needed).",
             "See strongestArgumentAgainst field above (also populated in dedicated field).",
             "", "N/A", "see above"):
    ok(dr.is_nonanswer(_ptr), "a pointer where an argument was required is caught: %r" % _ptr[:52])
_real = ("Selection bias is the live risk here: see the coverage gaps above for which "
         "sub-questions went unanswered, and note that the two largest trials shared an "
         "author team, so the pooled estimate may be one lab's result counted twice.")
ok(not dr.is_nonanswer(_real),
   "while an argument that CITES another section mid-sentence is left alone - the rule "
   "needs a pointer AND a short field, because either alone would be wrong")
# The length test is gone. It broke in BOTH directions: a 308-character padded pointer
# passed, and a 144-character genuine argument opening "See above for the coverage gaps"
# was replaced with "NOT PRODUCED" - the check deleting real evidence.
ok(not dr.is_nonanswer("See above for the coverage gaps; the deeper risk is that both "
                       "trials shared an author team, so the pooled estimate may be one "
                       "lab counted twice."),
   "a genuine argument that OPENS by citing another section survives - a terse argument "
   "and a padded pointer are the same length, so length could never separate them")
ok(dr._NONANSWER_MIN_WORDS == 8,
   "what is judged is what REMAINS once the pointer is stripped: four words of "
   "parenthetical is not an argument, a clause is (floor=%d)" % dr._NONANSWER_MIN_WORDS)
ok(not dr.is_nonanswer("See strongestArgumentAgainst field above (duplicate not needed). "
                       + "This note is retained for completeness and does not itself "
                         "contain the argument. " * 3),
   "and the permissive direction is NAMED, not claimed closed: a pointer followed by "
   "enough filler still passes, because no lexical rule separates filler from argument")

_ptrrep = run({"pointer_steelman": True}, q="Does the re-ask recover the steelman?")
ok(not dr.is_nonanswer(_ptrrep.get("strongestArgumentAgainst")),
   "when synthesis returns a pointer, ONE more call is made for that field alone and the "
   "argument is recovered")
ok("university" in (_ptrrep.get("strongestArgumentAgainst") or ""),
   "and it is the re-asked text that lands in the report, not the pointer")
ok("noSteelman" not in (_ptrrep.get("honestLimits") or {}),
   "with no false alarm in honestLimits when the recovery worked")

_hardrep = run({"pointer_steelman_hard": True}, q="Does a failed re-ask get disclosed?")
ok("NOT PRODUCED" in (_hardrep.get("strongestArgumentAgainst") or ""),
   "and when the re-ask ALSO returns a pointer, the field says so plainly instead of "
   "publishing a cross-reference that reads like content")
ok("noSteelman" in (_hardrep.get("honestLimits") or {}),
   "the limit travels with the report, so a reader of the pasted JSON sees that the "
   "conclusion stands unopposed")

print("\n-- a CALIBRATED run reaches the end, not just the calibration --")
# The path no test ever ran. Every calibration test until now called
# deepresearch/calibration.py directly or asserted on a line of engine source, so the
# calibration BLOCK INSIDE deepresearch() was never executed end to end. It bound an int
# to `dropped` - a name already holding the URL-dedup list in that same 486-line scope,
# which stats() closes over to publish `budgetDropped=len(dropped)`. Every calibrated run
# therefore died with `TypeError: object of type 'int' has no len()` at the final step,
# after framing, two search waves, 30 verified claims, the dropped sample, the citation
# audit and the calibration itself had all succeeded. Found by running the tool for real.
_prev_cal, _prev_drop = dr.CALIBRATE_N, dr.SAMPLE_DROPPED_N
try:
    dr.CALIBRATE_N, dr.SAMPLE_DROPPED_N = 6, 3
    _calrep = run(depth="standard", q="Does a calibrated run survive to the report?")
finally:
    dr.CALIBRATE_N, dr.SAMPLE_DROPPED_N = _prev_cal, _prev_drop

ok(isinstance(_calrep, dict) and not _calrep.get("error"),
   "a run with --calibrate AND --sample-dropped produces a report at all")
ok(isinstance((_calrep.get("stats") or {}).get("budgetDropped"), int),
   "stats.budgetDropped is an int - the calibration counter no longer shadows the "
   "URL-dedup list that stats() closes over")
ok(_calrep.get("calibration"),
   "and the calibration block still publishes its result")
ok(isinstance((_calrep.get("calibration") or {}).get("excludedForLensErrors"), int),
   "excludedForLensErrors is the COUNT of claims an errored lens call removed, not the "
   "list it was accidentally sharing a name with")
ok(isinstance(_calrep.get("droppedSample"), dict) or _calrep.get("droppedSample") is None,
   "and the dropped-claim sample survives to the report beside it")

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

print("\n-- the provider seam: selection, transport facts, and honest errors --")
# ADR-0004. The CLI was born on Anthropic (API key or a Claude Code OAuth login) with
# the provider as seven module constants; GLM 5.3 is the second adapter, which makes
# the seam real. These pin the three things that must hold: unset means Anthropic
# BYTE FOR BYTE, a GLM key alone means GLM with GLM facts in every error, and two
# set keys are refused aloud rather than resolved by dict order.
import deepresearch.providers as _P   # noqa: E402
import json as _pj  # noqa: E402

def _with_env(env, fn):
    """Run fn under a mutated environment, restoring exactly what was there."""
    # Hermetic: clear EVERY selector input (DR_* and all provider keys), not just the
    # ones this call passes - otherwise the block reads the developer's real
    # ~/.claude login or shell key and passes locally while raising on CI. That is
    # exactly the environment-dependent test this repo treats as no test at all
    # (caught by CI 2026-09-15: the BASE_URL-override case called transport() with no
    # key and silently borrowed the local Claude Code login to succeed).
    _clear = ("DR_PROVIDER", "DR_MODEL", "DR_TRANSPORT", "ANTHROPIC_API_KEY",
              "ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_BASE_URL", "GLM_BASE_URL",
              "DR_GLM_HARNESS")
    _saved = {k: _os.environ.get(k) for k in list(env) + list(_clear)}
    for k in _clear:
        _os.environ.pop(k, None)
    for k, v in env.items():
        if v is None:
            _os.environ.pop(k, None)
        else:
            _os.environ[k] = v
    try:
        _P.reset()
        return fn()
    finally:
        for k, v in _saved.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v
        _P.reset()

ok(_with_env({}, lambda: _P.select()["name"]) == "claude",
   "nothing set selects claude, the contract default - an unused option must not "
   "perturb the configuration the prompts were calibrated against")
ok(_with_env({"ZAI_API_KEY": "k"}, lambda: _P.select()["name"]) == "glm",
   "a lone ZAI_API_KEY infers glm: the one-env-var run, no new concepts to learn")
ok(_with_env({"GLM_API_KEY": "k"}, lambda: _P.select()["name"]) == "glm",
   "GLM_API_KEY is accepted as an alias and infers glm too")
ok(_with_env({"DR_PROVIDER": "glm"}, lambda: _P.select()["name"]) == "glm",
   "DR_PROVIDER explicit wins even with no key set (credential loads later, at transport)")
try:
    _with_env({"DR_PROVIDER": "sonnet"}, lambda: _P.select())
    ok(False, "an unknown DR_PROVIDER must be refused")
except dr.AuthError as e:
    ok("sonnet" in str(e) and "claude" in str(e) and "glm" in str(e),
       "an unknown DR_PROVIDER is refused listing the valid names - a typo must not "
       "fall through to inference and bill a different account")
try:
    _with_env({"ANTHROPIC_API_KEY": "a", "ZAI_API_KEY": "b"}, lambda: _P.select())
    ok(False, "both keys set must be refused")
except dr.AuthError as e:
    ok("ANTHROPIC_API_KEY" in str(e) and "ZAI_API_KEY" in str(e) and "DR_PROVIDER" in str(e),
       "two set key variables are refused ALOUD, naming both and the way out - "
       "guessing by dict order would bill the wrong account")

_glm = _with_env({"ZAI_API_KEY": "sk-glm"}, lambda: _P.transport())
ok(_glm["url"].startswith("https://api.z.ai/") and _glm["url"].endswith("/v1/messages"),
   "the glm transport targets the Anthropic-compatible endpoint")
ok(_glm["headers"].get("x-api-key") == "sk-glm" and "anthropic-beta" not in _glm["headers"],
   "glm authenticates with a plain key and carries no Claude Code OAuth beta headers - "
   "impersonating claude-cli at a third-party endpoint would be a lie in the wire")
ok(_glm["default_model"] == "glm-5.3", "glm's default model is glm-5.3")
ok("GLM" in _glm["system_prefix"] and "Claude Code" not in _glm["system_prefix"],
   "glm's identity block tells the truth about who is talking - the Claude Code "
   "prefix on a GLM run would be the same overclaim the labels keep making")
try:
    _with_env({"DR_PROVIDER": "glm"}, lambda: _P.credential())  # no glm key set
    ok(False, "glm with no key must raise")
except dr.AuthError as e:
    ok("ZAI_API_KEY" in str(e) and "ANTHROPIC" not in str(e),
       "a GLM run short a key is told to set ZAI_API_KEY, never ANTHROPIC_API_KEY - "
       "preflight and selftest quote these messages verbatim")

_claude = _with_env({"ANTHROPIC_API_KEY": "sk-ant", "DR_TRANSPORT": "http"}, lambda: _P.transport())
ok(_claude["url"] == "https://api.anthropic.com/v1/messages"
   and _claude["headers"] == {"content-type": "application/json",
                              "anthropic-version": "2023-06-01",
                              "x-api-key": "sk-ant"},
   "the unset-anthropic path is BYTE-IDENTICAL to the pre-seam constants: same URL, "
   "same three headers - the rewrite bought GLM without spending any Claude behaviour")
ok(_with_env({"ANTHROPIC_API_KEY": "k", "DR_TRANSPORT": "http",
                "ANTHROPIC_BASE_URL": "https://relay.example"},
             lambda: _P.transport()["url"]) == "https://relay.example/v1/messages",
   "ANTHROPIC_BASE_URL still overrides the claude endpoint (relays, proxies)")
ok(dr.CC_SYSTEM_PREFIX == "You are Claude Code, Anthropic's official CLI for Claude.",
   "the Claude identity constant survives under its old name for anything grepping for it")

# The contract is data, so it can be WRONG in a way code review cannot see: a provider
# row missing its endpoint or key env would select fine and fail at the first call.
# Same shape as the tier contract check in CI.
_pc = _pj.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                  "contract", "providers.json"), encoding="utf-8"))
ok(_pc.get("default") in _pc.get("providers", {}),
   "providers.json names a default that exists")
for _pname, _prow in _pc["providers"].items():
    ok(_prow.get("baseUrl", "").startswith("https://")
       and _prow.get("keyEnvs") and _prow.get("defaultModel") and _prow.get("systemPrefix"),
       "provider %r carries endpoint, key envs, default model and an identity block" % _pname)

# The CLI surface of the same rules: a bad DR_PROVIDER and a two-key ambiguity must
# refuse with the house error shape (JSON, exit 2) rather than an import-time
# traceback, and --help must work under a bad env because the package imports for it.
import subprocess as _sp
_r = _sp.run([sys.executable, "-m", "deepresearch", "--question", "x"],
             capture_output=True, text=True, env=dict(_os.environ, DR_PROVIDER="bogus"),
             cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ok(_r.returncode == 2 and "bogus" in _r.stdout and "claude" in _r.stdout and "glm" in _r.stdout,
   "a bad DR_PROVIDER refuses with JSON + exit 2 naming the valid providers - not an "
   "import-time traceback")
_r2 = _sp.run([sys.executable, "-m", "deepresearch", "--help"], capture_output=True,
              text=True, env=dict(_os.environ, DR_PROVIDER="bogus"),
              cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ok(_r2.returncode == 0 and "--provider" in _r2.stdout,
   "--help still works under a bad DR_PROVIDER: the import falls back provisionally "
   "and only main() refuses")

# The env shim, audited live 2026-09-15 on the Telegram deployment: gateways map a Z.ai
# plan key into ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL. The seam used to describe that
# as "Anthropic (api-key)" while POSTing to api.z.ai with model name claude-sonnet-5 -
# a name Z.ai tolerates by luck. When the override host matches a CONTRACT provider,
# the default model follows the endpoint and describe() says whose endpoint it is.
_shim = _with_env({"ANTHROPIC_API_KEY": "k", "DR_TRANSPORT": "http",
                   "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"},
                  lambda: (_P.describe(), _P.select()["default_model"]))
ok("Z.ai GLM" in _shim[0] and _shim[1] == "glm-5.3",
   "the env shim is described truthfully: describe() names Z.ai as the endpoint and "
   "the default model follows the endpoint (glm-5.3), not the credential that selected "
   "claude - a model name that only worked by Z.ai's tolerance")
_relay = _with_env({"ANTHROPIC_API_KEY": "k", "DR_TRANSPORT": "http", "ANTHROPIC_BASE_URL": "https://relay.internal"},
                   lambda: (_P.describe(), _P.select()["default_model"], _P.select()["endpoint_owner"]))
ok(_relay[1] == "claude-sonnet-5" and _relay[2] is None,
   "a generic relay host matches no contract provider, so nothing is adopted - a "
   "proxy address is not evidence of anyone's model semantics")
_forced = _with_env({"ANTHROPIC_API_KEY": "k", "DR_TRANSPORT": "http",
                     "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
                     "DR_MODEL": "glm-5.3-air"},
                    lambda: (_P.select()["default_model"], _P.select()["endpoint_owner"]))
ok(_forced[0] == "claude-sonnet-5" and _forced[1] == "glm",
   "an explicit DR_MODEL suppresses model adoption but NOT the disclosure: the default "
   "stays claude-sonnet-5 (the caller chose a model; the seam does not second-guess), "
   "while describe() still says whose endpoint the wire goes to")

# The ZCode skill is an executable protocol: a function name or field name it mentions
# that does not exist in the engine is a bug a reader cannot see. Audited 2026-09-15:
# it validated array replies against a per-object schema (every valid lens verdict
# flagged), skipped citable_only (T5 farms in the verify pool), named a nonexistent
# factOrInference field, and fed _evidence_base rows with no claims counts. This test
# greps the skill's engine vocabulary against the engine itself, so the next drift is
# a red test rather than a failed run.
_zk = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "integrations", "zcode", "SKILL.md"), encoding="utf-8").read()
_zsyms = sorted(set(_re.findall(r"\b((?:p_|S_)[A-Za-z_]+|quote_span|tier_of|shape|"
                                r"coverage_balanced|citable_only|_hyp_mismatch|"
                                r"_evidence_base|REFUTATIONS_REQUIRED)\b", _zk)))
_missing = [s for s in _zsyms if not hasattr(dr, s)]
ok(_zsyms and not _missing,
   "every engine symbol the ZCode skill names exists in the engine (%d checked%s)"
   % (len(_zsyms), ("; missing: " + ", ".join(_missing)) if _missing else ""))
ok("factInferenceAssumption" in _zk and "factOrInference " not in _zk,
   "the skill names the synthesis field by its real name, factInferenceAssumption")
ok("'verdicts'" in _zk and "run `citable_only` FIRST" in _zk,
   "the array-wrapper validation and the citable_only-before-ranking gate are both in "
   "the protocol - the two audited shape bugs")
ok("BEFORE dispatching the critics" in _zk,
   "artifacts are persisted before critique - the live run's recorded defect")
# The fifth reversal of the negation check, pinned. v1.10.0 symmetric -> accused the
# null; v1.10.1 ADD-only -> opened the surgical-delete mirror; v1.11.0 symmetric again
# -> re-accused the null (verified live by audit 2026-09-15 against runs/v10); now
# direction-aware on the only axis that separates: character similarity. Attacks
# 0.821-0.977, faithful compact rewordings 0.479-0.697, bar 0.75. The synonym-swap
# rewording at 0.855 is inseparable from the attack band and is a NAMED LIMIT: it
# fires, and pays only the label - the stamp survives via the text path.
ok(dr._negation_differs("Minimum wage increases do not reduce teen employment",
                        "Minimum wage increases reduce teen employment"),
   "ADD direction fires categorically - a rewording never gains a negator")
ok(dr._negation_differs("The intervention has an effect on employment",
                        "The intervention has no effect on employment"),
   "surgical DELETE fires: near-identical text, opposite claim (the v1.11 mirror stays closed)")
ok(dr._negation_differs("Minimum wage increases reduce teen employment",
                        "Minimum wage increases do not reduce teen employment"),
   "and the registered-'do not' direction too - the conformance-pinned attack")
_v10d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                    "runs", "v10-hypothesis-matching.json"))
                  ) if False else None
import json as _j2
_v10 = _j2.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                  "runs", "v10-hypothesis-matching.json")))
ok(all(not dr._hyp_mismatch(dr._hyp_key(v["hypothesis"]), dr._hyp_key(h["hypothesis"]))
       for h, v in zip(_v10["scopeContract"]["hypotheses"], _v10["hypothesisVerdicts"])),
   "the v1.10.1 regression is fixed: all four v10 verdicts pass the number-path check, "
   "including the faithful rewording of the null H1 - v1.11.0 re-accused it")
ok(not dr._negation_differs("IF and CCR produce statistically similar fat loss under matched calorie deficits",
                            "No meaningful difference: under matched calorie deficits, IF and CCR produce "
                            "statistically similar fat loss, and the difference is adherence, not metabolic superiority"),
   "a COMPACT rewording of a null (0.48-0.70 similarity) is not accused - the good reference")
_nl_v = "H1: Under matched calorie deficits, IF and CCR produce statistically similar fat loss; the difference is adherence rather than metabolic superiority"
_nl_r = "No meaningful difference: under matched calorie deficits, IF and CCR produce statistically similar fat loss, and the difference is adherence, not metabolic superiority"
ok(dr._negation_differs(_nl_v, _nl_r)
   and not dr._same_hypothesis(dr._hyp_key(_nl_v), dr._hyp_key(_nl_r)),
   "the NAMED LIMIT, pinned with its exact cost: the synonym-swap rewording ('not X' -> "
   "'rather than X', 0.855) sits inside the attack band and fires in BOTH the number and "
   "text paths - so it is marked post-hoc and loses the stamp. That is the UNDERSTATING "
   "direction the repo's policy accepts, but note: v1.11's docstring claimed this shape "
   "kept its stamp via the text path - false in its own shipped code, which gated both "
   "paths with the same symmetric check")

# SESSION TRANSPORT (ADR-0005). The owner's deployments hold no API keys: model calls
# are powered by a harness CLI's own login - `claude -p` for the claude provider,
# `hermes -p glm -z` for zai. Session-first: if the harness resolves on the machine,
# IT is the power source; key-env HTTP is the fallback for headless servers; DR_TRANSPORT
# forces either way. These tests are hermetic: shutil.which is stubbed so no harness is
# ever spawned and no login is ever read.
import shutil as _shutil
def _with_harness(fake_which, env, fn):
    """Run fn with which() lying about which harnesses exist, env cleared, restored."""
    _real_which = _P.shutil.which
    _P.shutil.which = fake_which
    try:
        return _with_env(env, fn)
    finally:
        _P.shutil.which = _real_which

_nothing = lambda c: None                     # no harness on this machine
_claude_only = lambda c: "/usr/bin/claude" if c == "claude" else None

ok(_with_harness(_claude_only, {"DR_PROVIDER": "claude"}, lambda: _P.transport()["scheme"]) == "session",
   "claude on PATH -> session transport: the login-powered CLI IS the intended source, "
   "no credential is read at all")
ok(_with_harness(_claaude_only := (lambda c: "/usr/bin/claude" if c == "claude" else None),
                 {"DR_PROVIDER": "claude"}, lambda: _P.transport()["harness_argv"])
   == ["claude", "-p"],
   "the claude adapter spawns exactly `claude -p` + prompt - the verified shape")
_glm_env = {"DR_PROVIDER": "glm", "DR_GLM_HARNESS":
            "docker exec hermes-agent /opt/hermes/.venv/bin/hermes"}
_glm_argv = _with_harness(lambda c: "/usr/bin/docker" if c == "docker" else None,
                          _glm_env, lambda: _P.transport()["harness_argv"])
ok(_glm_argv is not None and _glm_argv[:4] == ["docker", "exec", "hermes-agent",
                                               "/opt/hermes/.venv/bin/hermes"]
   and _glm_argv[4:] == ["-p", "glm", "-z"],
   "the zai adapter spawns `hermes -p glm -z` - via the container where hermes lives, "
   "the verified shape; hermes holds the credential, deepresearch holds nothing")
ok(_with_harness(_nothing, {"DR_PROVIDER": "glm", "ZAI_API_KEY": "k"},
                 lambda: _P.transport()["scheme"]) == "api-key",
   "no harness resolvable -> the seam falls back to the credential path (HTTP), which "
   "is the headless-server story")
ok(_with_harness(_claude_only, {"DR_PROVIDER": "claude", "ANTHROPIC_API_KEY": "k",
                                "DR_TRANSPORT": "http"},
                 lambda: _P.transport()["scheme"]) == "api-key",
   "DR_TRANSPORT=http forces HTTP even with the harness present: a user holding both "
   "may prefer one socket to 150 spawns")
_d = _with_harness(_claude_only, {"DR_PROVIDER": "claude"}, lambda: _P.describe())
ok("session via claude -p" in _d and "no API key" in _d,
   "describe() names the session honestly: %r" % _d)
_sp = dr._session_prompt({"system_prefix": "PREFIX"}, "QUESTION", {"type": "object"})
ok(_sp.startswith("PREFIX") and "ONE JSON object" in _sp and "QUESTION" in _sp,
   "the session prompt flattens the whole agent() contract: identity, JSON-only "
   "instruction, schema verbatim, then the task")
for text, want in [('junk ```json\n{"refuted": true}\n``` trailing', {"refuted": True}),
                   ('Answer: {"reply": "ok"} thanks', {"reply": "ok"}),
                   ('no json', None), ('[1,2]', None)]:
    ok(dr._extract_json(text) == want, "extractor: %r -> %r" % (text[:24], want))
# retry policy over a spawn: first reply is prose, second is JSON - the corrective
# re-ask must fire and the shaped result must come back (policy lives in agent(), ADR-0001)
_spawns = iter(["I will not use JSON, sorry.",
                '{"reply": "pong"}'])
def _fake_run(argv, prompt, timeout=300):
    _sp = next(_spawns)
    return _sp
_real_run = _P.run_harness
_P.run_harness = _fake_run
try:
    _saved_t = _P._TRANSPORT
    _P._TRANSPORT = dict(_P.spec("claude"), scheme="session", secret=None, via=None,
                         headers=None, harness_argv=["claude", "-p"])
    _r = _REAL_AGENT("test", {"type": "object", "required": ["reply"],
                           "properties": {"reply": {"type": "string"}}}, label="t", retries=2)
    ok(_r == {"reply": "pong"},
       "a prose reply triggers the corrective re-ask and the second spawn's JSON is "
       "shaped and returned - the same policy as HTTP, no coercion")
finally:
    _P.run_harness = _real_run
    _P._TRANSPORT = _saved_t

# STDIO TRANSPORT (ADR-0005, third transport): the driving session window IS the
# model. One JSON request per call on stdout, one id-matched reply on stdin, zero
# spawns, zero credentials. Hermetic: stdin/stdout are swapped for pipes and a
# scripted harness answers - the fifo pattern verified live 2026-09-16 before this
# suite existed.
ok(_with_env({"DR_PROVIDER": "glm", "DR_TRANSPORT": "stdio"},
             lambda: _P.current_scheme()) == "stdio",
   "DR_TRANSPORT=stdio selects the third transport before any harness lookup")
ok("THIS WINDOW is the model" in _with_env({"DR_PROVIDER": "glm", "DR_TRANSPORT": "stdio"},
                                           lambda: _P.describe()),
   "describe() says who powers stdio: the driving window, no key, no spawn")
import io as _io
import json as _js
def _stdio_roundtrip(replies):
    """Feed agent() scripted id-matched replies through real pipes."""
    import deepresearch.engine as _E2
    _in_r, _in_w = os.pipe()      # engine reads answers from here
    _out_r, _out_w = os.pipe()    # engine writes requests here
    _saved_in, _saved_out = _E2.sys.stdin, _E2.sys.stdout
    _E2.sys.stdin = os.fdopen(_in_r, "r")
    _E2.sys.stdout = os.fdopen(_out_w, "w")
    # scripted harness thread: read a request line, write the next scripted reply
    import threading as _th
    def _harness():
        f = os.fdopen(_out_r, "r")
        for line in f:
            req = _js.loads(line)
            spec_reply = replies.pop(0) if replies else None
            if spec_reply is None:
                ans = {"id": req["id"], "reply": {"reply": "pong"}}
            elif spec_reply.get("id") == "mismatch":
                ans = {"id": req["id"] + 100, "reply": spec_reply["reply"]}
            else:
                ans = {"id": req["id"], "reply": spec_reply.get("reply", {"reply": "pong"})}
            os.write(_in_w, (_js.dumps(ans) + "\n").encode())
        f.close()
    _t = _th.Thread(target=_harness, daemon=True); _t.start()
    _saved_tr = _P._TRANSPORT
    # Pin the transport (as the session retry test does): the exchange is under test,
    # not resolution - which the pure tests above already cover. Relying on ambient
    # env made this test demand a credential on CI (no harness, no key, no login).
    _P._TRANSPORT = dict(_P.spec("glm"), scheme="stdio", secret=None, via=None,
                         headers=None, harness_argv=None)
    try:
        return _REAL_AGENT("probe", {"type": "object", "required": ["reply"],
                                     "properties": {"reply": {"type": "string"}}},
                           label="stdio-suite", retries=3)
    finally:
        _P._TRANSPORT = _saved_tr
        _E2.sys.stdin.close(); _E2.sys.stdout.close()
        _E2.sys.stdin, _E2.sys.stdout = _saved_in, _saved_out

import json as _j3
_r = _stdio_roundtrip([{"id": 1, "reply": {"reply": "pong"}}])
ok(_r == {"reply": "pong"},
   "a matching-id JSON reply on stdin is shaped and returned - the verified fifo pattern")
_r2 = _stdio_roundtrip([{"id": "mismatch", "reply": {"reply": "wrong-id"}}])
ok(_r2 == {"reply": "pong"},
   "a mismatched-id reply is refused (None for that attempt) and the retry exchange "
   "succeeds on the next id - correlation is by id, not by order alone")

# E2E-run fixes (2026-09-16, stdio transport test with a minimal custom depth).
ok("max(3, T[\"perspectives\"])" in _ENG,
   "the plan ASKS for at least the schema floor of 3 perspectives, so a depth contract "
   "with fewer cannot produce a contradictory prompt that burns the retry budget - "
   "found live: a 2-perspective depth yielded three identical schema violations")
ok("quick depth runs no gap " in _ENG and "Not scored" in _ENG,
   "a quick-depth report SAYS its coverage table was never scored, rather than "
   "rendering an empty table indistinguishable from a scored-and-silent one")
import subprocess as _sp2
_r_bg = _sp2.run([sys.executable, "-m", "deepresearch", "--question", "x", "--bg"],
                 capture_output=True, text=True, env=dict(_os.environ, DR_PROVIDER="glm",
                                                          DR_TRANSPORT="stdio"),
                 cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ok(_r_bg.returncode == 4 and "incompatible" in _r_bg.stdout and "stdout" in _r_bg.stdout,
   "--bg under DR_TRANSPORT=stdio is refused in the parent with a visible JSON error "
   "(exit 4) - the detached child's stdout is the request stream and would be silently "
   "redirected to a log while the parent reported success")

print("\n-- the hermes skill-drift warning: one string, three surfaces, never a gate --")
# 2026-09-16: agents kept being served a v1.9.2 skill through four repo releases because
# hermes' loader ignores symlinks and a real-file copy in the glm profile outranked every
# symlinked "source of truth". The deployment now runs on real files + sync-skill.sh; this
# is the engine-side tripwire. Effect tests: build real trees in a temp HERMES_HOME.
import tempfile as _tmp2, subprocess as _sp3  # noqa: E402
_V = dr_pkg.__version__
_DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "integrations", "hermes", "SKILL.md")

def _mk_tree(root, rel, version):
    p = os.path.join(root, rel)
    os.makedirs(p, exist_ok=True)
    with open(os.path.join(p, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: deepresearch\nversion: %s\n---\nbody\n" % version)
    return p

with _tmp2.TemporaryDirectory() as _hh:
    _mk_tree(_hh, "skills/research/deepresearch", _V)
    _mk_tree(_hh, "profiles/glm/skills/research/deepresearch", "1.9.2")
    _mk_tree(_hh, "profiles/other/skills/research/deepresearch", "0.0.1")
    _w = _with_env({"HERMES_HOME": _hh}, dr.skill_drift_warning)
    ok(_w and "profiles/glm" in _w and "1.9.2" in _w and "profiles/other" in _w
       and "sync-skill.sh" in _w,
       "a drifted profile tree is named per-tree in the warning, with the stale version, "
       "the current one, and the remedy command")
    ok(_w and (os.path.join(_hh, "skills", "research", "deepresearch") + " is") not in _w,
       "a CURRENT tree (the shared root, at engine version) is not accused")
    _mk_tree(_hh, "profiles/glm/skills/research/deepresearch", _V)
    _mk_tree(_hh, "profiles/other/skills/research/deepresearch", _V)
    ok(_with_env({"HERMES_HOME": _hh}, dr.skill_drift_warning) is None,
       "all trees current -> None, not an empty string (surfaces check `is not None`)")
    # Absent tree: silence, not accusation - sync-skill.sh creates it.
    os.remove(os.path.join(_hh, "profiles/other/skills/research/deepresearch/SKILL.md"))
    ok(_with_env({"HERMES_HOME": _hh}, dr.skill_drift_warning) is None,
       "an absent tree is a silent skip: absence is nothing to disagree with")
ok(_with_env({"HERMES_HOME": None}, dr.skill_drift_warning) is None,
   "no HERMES_HOME -> only the doc-vs-engine compare, which agrees in this repo -> None")
# The parser itself: quotes, body-versions, absent files.
with _tmp2.TemporaryDirectory() as _pd:
    _q = os.path.join(_pd, "SKILL.md")
    with open(_q, "w", encoding="utf-8") as f:
        f.write('---\nname: x\nversion: "9.9.9"\n---\nversion: 0.0.0\n')
    ok(dr._frontmatter_version(_q) == "9.9.9",
       "frontmatter version is unquoted, and a version: in the BODY cannot pose as the tag")
    with open(_q, "w", encoding="utf-8") as f:
        f.write("no frontmatter at all\nversion: 1.0\n")
    ok(dr._frontmatter_version(_q) is None, "a file with no frontmatter has no version")
    ok(dr._frontmatter_version(os.path.join(_pd, "nope.md")) is None,
       "an absent file reads as None, never raises")

# The wiring: the same string must reach all three surfaces (stderr at launch, the --bg
# handle, the report base) - checked on source shape because driving main() to completion
# needs model calls the suite refuses to make; the string's CONTENT is effect-tested above.
ok('print(_drift, file=sys.stderr)' in _main_src and '"skillDrift": _drift' in _main_src,
   "main() prints the drift to stderr and carries it in the --bg handle JSON")
ok("skillDrift=skill_drift_warning()" in _ENG,
   "the report base carries skillDrift, so all four exits persist it, not just the happy path")
ok("skill sync:" in _engine_txt.split("def selftest(", 1)[1].split("\ndef ", 1)[0],
   "selftest prints the plain skill-sync line (informational, never a failed check)")

# The deterministic gate and the watchdog, by EFFECT, as real subprocesses.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _run_sh(script, *args, **env):
    e = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    e.update(env)
    return _sp3.run(["sh", os.path.join(_REPO, "contrib", "hermes", script)] + list(args),
                    capture_output=True, text=True, env=e, timeout=60)

with _tmp2.TemporaryDirectory() as _gd:
    _mk_tree(_gd, "skills/research/deepresearch", _V)
    _mk_tree(_gd, "profiles/glm/skills/research/deepresearch", _V)
    _c = _run_sh("sync-skill.sh", "--check", _gd)
    ok(_c.returncode == 0 and "OK" in _c.stdout,
       "sync-skill.sh --check exits 0 with OK when doc==engine==trees")
    _mk_tree(_gd, "profiles/glm/skills/research/deepresearch", "1.9.2")
    _c = _run_sh("sync-skill.sh", "--check", _gd)
    ok(_c.returncode != 0 and "profiles/glm" in _c.stdout and "1.9.2" in _c.stdout,
       "one drifted tree -> nonzero, naming the tree and both versions")
    _i = _run_sh("sync-skill.sh", _gd)
    ok(_i.returncode == 0 and _V in _i.stdout,
       "install mode repairs the drift the check just caught (and reports the version it wrote)")
    _c = _run_sh("sync-skill.sh", "--check", _gd)
    ok(_c.returncode == 0, "and --check agrees afterwards: the gate and the fix share one definition of drift")
    # The watchdog: quiet when healthy, wakes on drift AND on an unreachable searxng.
    _srv2 = _serve(_ProbeJSON)
    _probe_url = "http://127.0.0.1:%d/search?format=json&q=test" % _srv2.server_address[1]
    _w0 = _run_sh("watchdog.sh", DR_REPO=_REPO, HERMES_HOME=_gd, DR_WATCHDOG_SEARXNG=_probe_url)
    ok(_w0.returncode == 0,
       "watchdog exits 0 (stays asleep, spends nothing) when trees are synced and searxng answers")
    _mk_tree(_gd, "profiles/glm/skills/research/deepresearch", "1.9.2")
    _w1 = _run_sh("watchdog.sh", DR_REPO=_REPO, HERMES_HOME=_gd, DR_WATCHDOG_SEARXNG=_probe_url)
    ok(_w1.returncode != 0 and "skill drift" in _w1.stdout,
       "watchdog wakes (nonzero + says why) on drift alone, even with searxng healthy")
    _w2 = _run_sh("watchdog.sh", DR_REPO=_REPO, HERMES_HOME=_gd,
                  DR_WATCHDOG_SEARXNG="http://127.0.0.1:9/search?format=json&q=x")
    ok(_w2.returncode != 0 and "searxng unreachable" in _w2.stdout,
       "watchdog wakes on an unreachable searxng from its vantage - the failure that "
       "silently degraded every gateway search to scholarly-only")
    _srv2.shutdown()

print("\n-- a dead general web must be impossible to miss (searchDegraded + banners) --")
# 2026-09-16, live under Hermes: every general-web backend returned zero while Crossref
# answered a job-board query with six DOI book chapters over HTTP 200; the run produced
# 13 confident sources of filler and the fact lived only in stats nobody opens. One
# condition at the seam (_general_web_dead) now feeds the report field, the synthesis
# banner, and the picker's refusal instruction - and the framing contract declares
# needsGeneralWeb so the picker knows when filler cannot substitute.
import json as _json3, tempfile as _tmp3  # noqa: E402
_REAL_SH = dr.search_health
def _health(**over):
    h = {"searxng": {"ok": True, "results": 0, "attempts": 3},
         "ddg-html": {"ok": True, "results": 0, "attempts": 2},
         "ddg-lite": {"ok": True, "results": 0, "attempts": 2},
         "mojeek": {"ok": True, "results": 0, "attempts": 1},
         "wikipedia": {"ok": True, "results": 4, "attempts": 3},
         "crossref": {"ok": True, "results": 6, "attempts": 3}}
    h.update(over)
    return lambda: h
try:
    dr.search_health = _health()
    ok(dr._general_web_dead() is True,
       "general-web 0-for-everyone while scholarly answers: the filler state is DETECTED")
    dr.search_health = _health(searxng={"ok": True, "results": 5, "attempts": 3})
    ok(dr._general_web_dead() is False,
       "any live general-web backend -> not degraded")
    dr.search_health = lambda: {}
    ok(dr._general_web_dead() is False,
       "no searches attempted at all -> not degraded (nothing tried, nothing lied about)")
    dr.search_health = _health()
    _hit = [{"url": "https://doi.org/10.1000/filler", "title": "A book chapter", "snippet": "unrelated"}]
    _pp = dr.p_pick("q", {"label": "L", "lens": "lens"}, _hit, needs_general_web=True)
    ok("general web is unreachable" in _pp and "Select NONE" in _pp,
       "the picker is told to refuse scholarly filler when the question needs the general web and it is dead")
    ok("general web is unreachable" not in dr.p_pick("q", {"label": "L", "lens": "lens"}, _hit,
                                                   needs_general_web=False),
       "a scholarly question gets no refusal note - the filler may be exactly its evidence")
    dr.search_health = _health(searxng={"ok": True, "results": 5, "attempts": 3})
    ok("general web is unreachable" not in dr.p_pick("q", {"label": "L", "lens": "lens"}, _hit,
                                                     needs_general_web=True),
       "healthy web -> no note even when the question needs it")
finally:
    dr.search_health = _REAL_SH
ok("searchDegraded=_general_web_dead()" in _ENG,
   "the report base carries searchDegraded, so all four exits persist it - same shape as skillDrift")
ok("THE GENERAL WEB WAS UNREACHABLE" in _ENG and "FIRST sentence of answerFirst" in _ENG,
   "the synthesis banner sits above the claims and commands the first sentence of answerFirst")
ok("needsGeneralWeb" in dr.S_FRAMING["required"] and
   dr.S_FRAMING["properties"]["needsGeneralWeb"] == {"type": "boolean"},
   "the framing contract declares needsGeneralWeb as a required boolean")
with _tmp3.TemporaryDirectory() as _cd:
    _cf = os.path.join(_cd, "c.json")
    with open(_cf, "w") as f:
        _json3.dump({"needsGeneralWeb": True}, f)
    ok(dr.load_contract(_cf) == {"needsGeneralWeb": True},
       "a supplied needsGeneralWeb is accepted by the intake and shaped to a real boolean")
    with open(_cf, "w") as f:
        _json3.dump({"needsGeneralWeb": "yes"}, f)
    try:
        dr.load_contract(_cf); ok(False, "a string needsGeneralWeb must be rejected")
    except dr.ContractError:
        ok(True, "a string needsGeneralWeb is rejected at intake, before any model call")

# The watchdog's searxng check must be a CONTENT check (HANDOVER §10): a suspended
# instance answers 200 with zero results, and a status-code check calls that healthy.
class _ProbeSuspended(_ProbeJSON):
    body = b'{"results": [], "unresponsive_engines": [["brave", "x"], ["google cse", "x"]]}'
class _ProbeGarbage(_ProbeJSON):
    body = b"<html>504 Gateway Timeout</html>"
_srv4, _srv5 = _serve(_ProbeSuspended), _serve(_ProbeGarbage)
with _tmp3.TemporaryDirectory() as _gd2:
    _mk_tree(_gd2, "skills/research/deepresearch", _V)
    _mk_tree(_gd2, "profiles/glm/skills/research/deepresearch", _V)
    _w3 = _run_sh("watchdog.sh", DR_REPO=_REPO, HERMES_HOME=_gd2,
                  DR_WATCHDOG_SEARXNG="http://127.0.0.1:%d/search?format=json&q=test" % _srv4.server_address[1])
    ok(_w3.returncode != 0 and "served 0 results" in _w3.stdout and "brave" in _w3.stdout,
       "watchdog wakes on a SUSPENDED instance: 200 + empty results names the suspended engines")
    _w4 = _run_sh("watchdog.sh", DR_REPO=_REPO, HERMES_HOME=_gd2,
                  DR_WATCHDOG_SEARXNG="http://127.0.0.1:%d/search?format=json&q=test" % _srv5.server_address[1])
    ok(_w4.returncode != 0 and "not JSON" in _w4.stdout,
       "watchdog wakes on a 200 whose body is not JSON - broken, not busy")
_srv4.shutdown(); _srv5.shutdown()

print("\n======== %d passed, %d failed ========" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

print("\n======== %d passed, %d failed ========" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
