# Quality review — do the research results lack quality?

Review date: 2026-09-20 (revised edition — every reader-flagged gap below is either now evidenced, reproduced, or explicitly marked unknown). Scope: the `deepresearch` engine (`deepresearch/engine.py`, `deepresearch/search.py`), the contract (`contract/depths.json`), the skill instructions (`integrations/zcode/SKILL.md`, `contrib/zcode-session/drive.sh`, `integrations/claude-code/deepresearch.js`), and the live run's verdict.

---

## 1. Executive answer

Yes — but the lack of quality is specific: per the supplied run verdicts (this review re-verified the code and reproduced the two decisive mechanics; it did not re-fetch the live pages), every audited Supabase citation re-verified verbatim on the live pages, yet the run shipped four critic-flagged unsupported summary insertions (one a fabricated mechanism), answered only one of the three providers asked about, and misattributed the gap to verification budget when its own sources array showed the claim pool was 100% Supabase from retrieval onward. The shipped insertions flow through a policy this review verified in code — critic-flagged sentences are reported, not removed, by default (`deepresearch/engine.py:94-101`) — while the incompleteness flowed through a degradation gate that a single early search result permanently mutes (reproduced this session, Appendix A) and a coverage table that is never reconciled after verification. The remaining confirmed defects make the same pattern systemic: the citation audit passes `partial` claims through a page window 2,000 characters smaller than the extractor's (reproduced this session, Appendix A), the "three adversarial lenses" are effectively two, verification scope is undisclosed at every depth, and the skill's two modes either void the advertised blindness (Mode A) or order enforcement by code that does not exist (Mode B).

---

## 2. Evidence, provenance, and what "verified" means

**Reviewed tree:** commit `f5232255e0407c33f8a628c22e3a9684a648d583` on `main` (`git rev-parse HEAD`, 2026-09-20; working tree clean except the untracked `out/` directory holding this report).

**"Verified" in this report means:** (a) every static code anchor cited below was re-read in that tree during this session and the quoted wording matches — engine.py:14-22, :75, :88-101, :258, :589-593, :988-992, :1124-1130, :1476-1479, :1556-1595, :1612, :1632-1641, :1831-1909, :2043-2099, :2245-2271, :2338-2345, :2359, :2429-2442, :2620-2683, :2752-2761, :2870-2887, :2915-2928, :2950, :2981-2999, :3005-3018, :3074-3137, :3156-3169, :3398-3407, :3408-3467, :3494, :3497-3506, :3715; search.py:106-125; depths.json:1-37; SKILL.md:3-8, :62-116, :160-199, :201-216; drive.sh:14-21; deepresearch.js:1626-1649; (b) the two dynamic checks were **re-run in this session** with the exact commands and outputs recorded in Appendix A; (c) live-run facts rest **solely on the two verdict texts supplied with the review ask** — this review did not re-fetch supabase.com, neon.com, or railway.com, and did not see the run's own report.

**One inherited naming error corrected:** the originating findings call the quote-locatedness function `quote_check`; no such function exists. The real function is `quote_span` (`deepresearch/engine.py:2043`; the skill itself names it correctly at `SKILL.md:216`). All mechanics attributed to "quote_check" check out against `quote_span`.

**Material that does not exist and could not be examined:** the live run's own report/artifact (not supplied; `runs/` was checked this session and contains no pricing-comparison run — newest is `v12-vitamin-d-respiratory.json`, Sep 15), the texts of the four shipped insertions (never enumerated by the verdicts), the cause of the in-run Neon fetch failures (never stated), and the run's mode and depth (never recorded). Every claim below that depends on these is marked **not established** rather than guessed.

---

## 3. Merged findings

The ten confirmed findings supplied to this review merge into eight (plus one session-verified gap, G1, that none of them covers). Mapping: **1+2 → M1** (audit-stage contract narrower than the extraction stage it audits) · **3 → M2** · **4 → M3** · **5+7 → M4** (verification-scope disclosure threshold-gated or absent) · **6 → M5** · **8 → M6** · **9 → M7** · **10 → M8**.

**Severity rubric.** `[high]` = the defect can put unsupported or fabricated content in front of the user, or can hide a degradation that changes how the report should be read (M1, M2, M3, M6, M7, G1). `[medium]` = the defect degrades the accuracy of the report's self-description — what was checked, what is covered — without itself gating content (M4, M5, M8). Severity grades the defect class; the §6 ranking grades contribution to the observed live failure, which is why a `[medium]` finding can rank above `[high]` ones and the unrated gap G1 ranks first.

### G1 — Critic-flagged summary sentences ship by default: the policy stops at reporting `[gap — session-verified, not among the ten findings]`

**Where:** `deepresearch/engine.py:94-101` (policy), `:3412-3448` (enforcement path), `:3449-3465` (what the report carries); `integrations/zcode/SKILL.md:196-199` (Mode B instruction), `:205-208` (presentation).
**What:** When the critic flags summary sentences that trace to no verified claim, the engine's default (`UNTRACEABLE_POLICY = os.environ.get("DR_UNTRACEABLE", "flag")`) is "report them and leave the text intact" — removal ("strike") exists but is opt-in via an environment variable. Mode B's instruction is the same discipline: "Report `untraceableCount` and the statements — not the critic's verdict tag." In both modes, the flagged text stays in the summary the user reads; the flags travel in a side channel (`processCritique`, and one of the "four numbers that must never be buried").
**Evidence:** Read this session — engine.py:95-96: `"flag"   report them and leave the text intact (default)` / `"strike"   remove them from the summary and record what was removed`; the strike branch at :3414-3442 executes only `if UNTRACEABLE_POLICY == "strike"`. Live corroboration (supplied verdict B): "its own critic flags four unsupported insertions, including a fabricated exceedance mechanism my live fetch confirms is on none of the cited pages, and the pipeline ships them anyway." This is the flagship live failure, and **none of the ten findings covers it** — M1's gate acts on audit verdicts for panel-surviving claims, a different layer that never saw these summary-level insertions.
**Fix:** The codebase's own measurement method closes the stated objection to striking — engine.py:3461-3462 records that on injected defects the critic "named all three" fabricated sentences — so measure the critic's precision properly, then default `DR_UNTRACEABLE` to `strike`; until then, render the flagged sentences themselves (not just a count) immediately beside the summary so the warning and the text cannot be read apart.

### M1 — The blind citation audit is built to pass the claims it exists to catch `[high]`

**Merged from:** findings 1 and 2 — one gate, two leaks with one root cause: the audit stage's evidence-and-verdict contract is narrower than the extraction stage it audits.
**Where:** `deepresearch/engine.py:3009-3018` (demotion set), `:3399-3407` (own admission), `:1872-1878` (honestLimits `partialCitationsAreKept`), `:3160-3166` (synthesis instructions 3-4 keep `partial`s with a warning sentence); the window mismatch at `:258`, `:2341`, `:1127`, `:2359`, `:2926`, `:2950`, `:1636`; the panel-facing assertion at `:1584-1585`.
**What:** Two mechanisms. **(a) `partial` never demotes.** Only `unsupported` removes a panel survivor; a `partial` verdict — "the statement adds scope, certainty or specificity the page does not carry" (the prompt's own definition, engine.py:1639-1640) — leaves the claim in the report, and the repo's own injected-defect measurement says `partial` is the auditor's dominant response to overstatement. **(b) The auditor sees a smaller page than every stage upstream.** The cap arithmetic, line by line: `web_fetch(url, cap=14000)` default (engine.py:258) — the sweep fetches at that default (engine.py:2341) and computes quote locatedness in code on the fetched text (engine.py:2359); the extractor's prompt carries `webtext(text, 13000)` (engine.py:1127); the audit refetches at `cap=12000, fresh=True` (engine.py:2926) and re-runs `quote_span` on that 12000-char view (engine.py:2950); the auditor's prompt carries `webtext(text, 12000)` (engine.py:1636). The plumbing between them: `_quote_line` (engine.py:1562-1585) renders the extraction-side result into the panel's verify prompt as "**Quote located on the page: YES** (100% of it, checked in code, not by a model)" (engine.py:1584-1585, injected at :1612) — so the panel is told the quote is genuine page text while the auditor, the only stage that can demote, cannot see past offset 12000. Support living in the last 2000 characters of the fetch is therefore invisible to the demotion layer: late-page support yields false `unsupported` kills, and a late-page contradiction lets a genuinely-retracted claim be certified off the top of the page.
**Evidence:** All anchors re-read this session (§2). The window mechanic **reproduced this session** — Appendix A, Probe 1: a quote at offset 12500 returns `located` (offset 12500, foundFraction 1.0) on the 14000-char view and `not-found` (foundFraction 0.0) on the auditor's 12000-char view, with `_quote_line` emitting "Quote located on the page: YES" for the panel. The injected-defect admission, verbatim (engine.py:3400-3404): "a tenfold inflated number, an invented '2019 Lancet consensus statement', and a claim widened to every adult on earth. All three would have been published." The design consciously *discloses* this (`partialCitationsAreKept`, engine.py:1872-1878) — disclosure is the mitigation, not a fix; the claims still ship.
**Fix:** One change-set to the audit contract — give the audit refetch and prompt view the same cap constant the sweep uses (one shared constant replacing the 14000/13000/12000 spread), and make every verdict that is not `supported` demote-or-restate: fold `partial` into the demotion set with a mandatory restatement pass instead of a warning sentence.

### M2 — The "three adversarial lenses" are effectively two `[high]`

**Merged from:** finding 3.
**Where:** `deepresearch/engine.py:2395-2402` (counter lens evidence), `:75` (`REFUTATIONS_REQUIRED = 2`), `:988-992` (no-refute-on-absence instruction), `:2429-2442` (kill count, inline in `run_panel`).
**What:** The counter-evidence lens judges from five search snippets of at most 240 characters (`webtext(h["title"], 110)`, `webtext(h["snippet"], 240)` — engine.py:2398-2400), never fetches a counter-source page, and is explicitly told "Do NOT refute merely because you found no counter-evidence" (engine.py:992). With the kill rule — `survives = len(valid) >= REFUTATIONS_REQUIRED and refuted < REFUTATIONS_REQUIRED` (engine.py:2435) — a counter lens that defaults to passing makes a kill require BOTH other lenses to refute: no redundancy, so any claim that is precisely hedged on an acceptably-tiered host survives regardless of shallowness.
**Evidence:** All anchors re-read this session; the snippet-only counter block at engine.py:2395-2402 contains no `web_fetch`; the kill count confirmed inline at engine.py:2430-2441.
**Fix:** Give the counter lens one real fetch — before voting, `web_fetch` its strongest counter-candidate (the same call the auditor uses) so a refutation can rest on a page and a kill no longer requires a 2-of-2 from the other two lenses.

### M3 — The dead-general-web gate cannot fire in the degradation it exists to flag `[high]`

**Merged from:** finding 4.
**Where:** `deepresearch/engine.py:3497-3506` (`_general_web_dead`), `:1104-1111` (pick warning), `:3107-3122` (synthesis banner), `:2665` (`searchDegraded` in the report base); `deepresearch/search.py:112-119` (cumulative counters).
**What:** Liveness is all-or-nothing over whole-run CUMULATIVE result counts (`tried and all((h.get(n) or {}).get("results", 0) == 0 for n in GENERAL_WEB)`, engine.py:3505-3506, over `GENERAL_WEB = ("searxng", "ddg-html", "ddg-lite", "mojeek")` at :3494), and `search.py:113-117` accumulates those counters for the process lifetime. A single early result from any one backend permanently mutes every degradation surface — banner, pick warning, `stats.searchDegraded`, the honestLimits caveat — precisely when nearly every search is challenged and falls through to Wikipedia/Crossref filler, the confident-but-wrong pool the gate was built to disclose (its own docstring, engine.py:3498-3503).
**Evidence:** Anchors re-read this session. **Reproduced this session** — Appendix A, Probe 2: with ddg-html at 39 `challenged` + 1 `ok` carrying 3 lifetime results (searxng/ddg-lite/mojeek all challenged), `_general_web_dead()` returns `False`; the identical state minus that single early success returns `True`. The one early result is the entire difference between disclosed and buried.
**Fix:** Judge liveness on a recency window or rate — e.g. zero general-web results in the last N searches of the current phase, or a success-rate threshold — instead of lifetime cumulative counts.

### M4 — The report never tells the user how much of its evidence was checked `[medium]`

**Merged from:** findings 5 and 7 — verification scope narrowed silently at every depth.
**Where:** `contract/depths.json:24-26` (quick), `:29`/`:33` (max_verify 30/50); `deepresearch/engine.py:2917` (audit gated on `T["audit"]`), `:1843-1906` (honestLimits keys — full list re-read this session), `:2624-2631` (verify cap), `:2264-2268` (tier-first ranking), `:3130-3135` (DROP_PCT ≥ 50 gate).
**What:** Two depths, one silence. **At quick depth** — which is opt-in, not the default: the CLI default is `standard` (engine.py:3715; depths.json's own header, lines 10-11: "Default depth is standard"; SKILL.md:31) — the blind audit, rescue and deepening never run (`"audit": false, "critics": 1, "rescue": false`, depths.json:25-26; gated at engine.py:2917), yet honestLimits (engine.py:1843-1906) carries no key saying the demotion layer never executed. The quick-depth coverage table does disclose its own absence ("Not scored: quick depth runs no gap analyst", engine.py:3081-3083) — nothing equivalent exists for the audit. **At every depth**, the verify pool is capped (`max_verify` 10/30/50, depths.json:25/:29/:33) and ranked tier-first, then by the extractor's self-rated importance (engine.py:2266-2268 — the comment itself concedes importance/sourceQuality are "the extractor grading its own work"), so a tangential T1/T2 claim is always verified before a central T3 in its bucket, most extracted evidence is silently never checked (the engine's own note: "The report rests on a fifth of the gathered evidence", engine.py:2756-2757), and the synthesis prompt is only forced to state the drop at ≥ 50% (engine.py:3135).
**Evidence:** All anchors re-read this session, including the complete honestLimits key list (evidenceBase, falseKillRateUnmeasured, reliabilityNotValidity, confirmedMeans, killRateMeans, quotesAreLocatedInCode, partialCitationsAreKept, framingProvenance, irrelevantSearchResults, archivedCopies, abstractOnlySources, searchCoverage — no audit-off or verifiedShare key).
**Fix:** Add unconditional honestLimits keys — `auditRan` (false at quick) and `verifiedShare` (verified/extracted) — rendered in every report, and state the dropped share whenever it is nonzero, not only at ≥ 50%.

### M5 — The coverage checklist is a pre-verification snapshot sold as final coverage `[medium]`

**Merged from:** finding 6.
**Where:** `deepresearch/engine.py:2596-2617` (Phase 4 deepen, pre-verify) vs `:2752` (Phase 5 verify) vs `:3076-3094` (rendered verbatim at synthesis); `:2653` (the snapshot rides the report via `base`); rescue at `:2871-2887`.
**What:** The "Coverage checklist status" table is the gap analyst's snapshot from before the adversarial panel runs, and it is never reconciled against kills or audit demotions — a sub-question whose claims were all killed (short of the zero-survivor rescue trigger, which itself only fires when `T["rescue"]` is on and never updates `coverage`) still reaches synthesis as "answered". The report can therefore claim coverage the filter already removed.
**Evidence:** All anchors re-read this session — `base = dict(..., coverage=coverage, ...)` at engine.py:2653; the render loop emitting the stored `c.get("status")` verbatim at engine.py:3086-3094; rescue's zero-survivor scope at engine.py:2871-2873.
**Fix:** Recompute the coverage table at synthesis from surviving claims (post-kill, post-audit), or stamp it with the phase it reflects and downgrade any sub-question whose survivors fell to zero.

### M6 — Mode A structurally voids the blindness and independence it advertises `[high]`

**Merged from:** finding 8.
**Where:** `integrations/zcode/SKILL.md:64-116` (Mode A; `:113` "Use Mode A unless python cannot run at all"; `:66-68` the guarantees), `:5-6` (headline promise), `:108-109` (blind-audit claim), `:163-164` ("The lenses never see each other"); `deepresearch/engine.py:18-19` (audit defined as "re-fetched in a context that never saw the original quote"), `:590` (`_session_prompt` tells the window "You are one worker in a multi-agent research harness" — false over stdio, where it is every worker); `contrib/zcode-session/drive.sh:16-18`.
**What:** In Mode A one driving window in one conversation plays extractor, all three "independent" lenses, the "blind" citation auditor, synthesis and critic. The window composed the quote itself in an earlier turn, so the audit is not blind and the three votes are self-anchored — while the user is told "every citation is re-checked blind against the live page" (SKILL.md:5-6) and "The lenses never see each other" (SKILL.md:163-164).
**Evidence:** All anchors re-read this session. The disclosure-terms grep was **re-run this session** (`grep -rniE 'one rater|same context|contaminat|independen'` over SKILL.md, drive.sh, docs/, deepresearch.js): the only admissions of the one-rater design are `drive.sh:18` ("one window is one rater") and `docs/adr/0005-session-transport.md:43` — an internal ADR, not a user-facing surface; all other hits are unrelated uses of "independent" in rater instructions. No report surface discloses it (the report records only `stats.transport`, engine.py:2681).
**Fix:** At minimum, emit an honestLimit in every Mode A report — "all roles shared one context; audit blindness and lens independence were not enforced" — and, properly, route the audit (and at least one lens) through a fresh session/subprocess so the auditing context never saw the quote.

### M7 — Mode B's two content-deciding steps are ordered "in code" — and no code exists `[high]`

**Merged from:** finding 9.
**Where:** `integrations/zcode/SKILL.md:164-165` (kill rule "in code"), `:176` ("Only `unsupported` demotes"), `:189-191` ("deterministic, in code"); the missing helpers: `deepresearch/engine.py:2430-2441` (inline kill count in `run_panel`), `:3009-3018` (inline demotion), `:2983-2998` (inline citationAccuracy) — vs importable `citable_only` (engine.py:2245), `coverage_balanced` (:2258), `_hyp_mismatch` (:1476), `_evidence_base` (:1792), all four confirmed importable module-level functions this session.
**What:** The skill pins every other deterministic step to a named import, but the two steps that decide content — the 2-of-3 kill tally and the audit demotion — exist only as inline pipeline logic a Mode B window cannot call, and unlike synthesis they get no caveat. What SKILL.md:184-187 actually says for synthesis, verbatim: "There is no importable builder for this one prompt — the instruction list lives inline in `_synthesize` (engine.py); transcribe it from there and re-check it against the engine when the repo changes. The seven builders that DO import are imported; this is the one place the no-paraphrase rule bends, and it says so." Steps 5 and 7 make the equivalent assertion ("in code", "deterministic, in code") with no builder and no caveat — a hand-orchestrating window will hand-count while believing it followed a code-checked rule.
**Evidence:** All anchors re-read this session, including the verbatim SKILL.md:184-187 text above and the inline kill count at engine.py:2430-2441.
**Fix:** Extract `kill_tally()` / `apply_demotion()` into importable helpers alongside `citable_only`/`_hyp_mismatch`/`_evidence_base` and cite them in SKILL.md — or add the same no-importable-builder caveat to steps 5 and 7 that synthesis already carries.

### M8 — Mode B's audit phase drops the engine's two hard-won audit rules `[medium]`

**Merged from:** finding 10.
**Where:** `integrations/zcode/SKILL.md:173-177` (phase 7); `integrations/claude-code/deepresearch.js:1630-1637` (full-pool rule) and `:1642-1647` (auditErrors rule); the Python engine's parallel at `deepresearch/engine.py:2993-2997`.
**What:** SKILL.md phase 7 never defines "the pool" — a survivors-only reading is available, which is exactly the rubber stamp the JS engine measured and documents: "Auditing only claims that three adversarial lenses already cleared made this a rubber stamp — it returned 100% on three consecutive live runs (7/7, 10/10, 15/15)" (deepresearch.js:1630-1632). And it has no rule for an auditor call that returned nothing, so a hand-orchestrating window can drop errored rows and publish an inflated citationAccuracy precisely when the run is degraded — the outcome the engine guards against: "Dropping it silently shrinks the denominator of the headline number exactly when the run is degraded" (deepresearch.js:1642-1644); the Python engine reports `auditErrors` outside the denominator and states the pool ("The pool is every verified claim, not survivors only", engine.py:2993-2997).
**Evidence:** All anchors re-read this session, including SKILL.md:173-177 (pool undefined; only "Only `unsupported` demotes") and both deepresearch.js passages.
**Fix:** Write both rules into phase 7 of SKILL.md: audit the FULL voted pool (survivors plus rescue claims), and count errored audit calls separately — never inside the citationAccuracy denominator.

---

## 4. What the live run actually produced

The run was asked to compare three providers (Supabase, Neon, Railway — free-tier terms and pricing ladder, with a winner to crown). Two verdict texts were supplied with this review; both are quoted verbatim below. **The run's mode and depth are not recorded in the supplied material** — this matters because the findings are mode- and depth-dependent (M4's audit-off applies only at quick depth; M6 describes Mode A, M7/M8 Mode B), and because which gate failed for the shipped insertions is mode-dependent: in the engine (Mode A or CLI) the demotion gate is the inline code of M1/M7 and critic flags are handled by G1's policy; in Mode B, per M7, demotion is hand-counted because no importable helper exists. What is mode-independent is G1: in both modes the default discipline is report-don't-remove, which is what the run exhibited.

> **Verdict A.** The Supabase half is genuinely verified: every published number traces to a located verbatim quote, and my live re-fetch of supabase.com/pricing and the corroborating blog confirmed all six audited quotes word-for-word — no fabrication reached the user. But the report answers only one of the three providers asked about, crowns no winner, and misdiagnoses why: it blames verification budget while its own sources array shows the extracted-claims pool was 100% Supabase from retrieval onward (Neon fetches failed, Railway was never fetched — both providers' pricing pages answered in a single live fetch during this audit). A careful human would trust the Supabase numbers and the candor, but would not accept this as an answer to the question asked; it is a well-documented one-third of one.

> **Verdict B.** A rigorously documented third of an answer: the Supabase slice is genuinely good — all eight quoteAudit citations re-verify verbatim on the live pages today, including the 500 MB hinge number and the four-plan $0/$25/$599 ladder — but the report fails the two standards that matter most, answering the question (Railway never fetched; Neon's live pricing page, one curl away, states the exact free-tier terms the report calls its missing hinge) and keeping the summary citation-clean (its own critic flags four unsupported insertions, including a fabricated exceedance mechanism my live fetch confirms is on none of the cited pages, and the pipeline ships them anyway). The self-audit is the best part of the artifact and would be superfluous in a report that acted on it.

**What the two verdicts agree on:** the audited Supabase citations were verbatim-clean on the live pages; the run answered one of three providers; no winner was crowned; the report's stated reason (verification budget) contradicts its own sources array; both missing providers' pages answered in a single live fetch during the audit.

**Where they materially differ, and the reconciliation (this review's reading of the two texts, not a claim either makes):** Verdict A says "no fabrication reached the user" — a sentence scoped to the audited citations it precedes ("confirmed all six audited quotes word-for-word — no fabrication reached the user"). Verdict B's centerpiece is four *unaudited* summary insertions — flagged by the critic, not the citation audit — shipping anyway, one of them a fabricated mechanism. Read together: the audit layer was clean, the summary-insertion layer was not, and a reader of Verdict A alone would rate the run materially better than the net verdict below. That split is exactly the two-layer shape G1 describes.

**Not established, and stated as such:**
- **The four insertions' texts.** Neither verdict quotes or enumerates them; the run's report was not supplied and is not in `runs/` (checked this session — see §2). The only identifying facts available: there are four, they are summary insertions flagged by the run's own critic, and one is a "fabricated exceedance mechanism" that the auditor's live fetch found on none of the cited pages. A future fix cannot be verified against exactly-those-four from this document.
- **Why the Neon fetches failed in-run.** Neither verdict names a cause (transient error, challenge, block, wrong URL). The only established facts: the in-run fetches failed, and one post-hoc live fetch succeeded during the audit. "Retrieval, not budget, was the binding constraint" is the verdicts' inference from that post-hoc fetch, not a diagnosed cause; M3 explains why the collapse was never *disclosed*, not why it happened.
- **Six vs eight audited citations.** Verdict A says six audited quotes, Verdict B says eight quoteAudit citations — consistent with two passes at the same question, but which number describes the artifact a reader holds can only be settled by counting the `quoteAudit` rows in that artifact. Both verdicts assert the citations were verbatim-clean, so the discrepancy does not change the quality verdict.

**What that says about quality.** The verified floor is high — no audited citation was fabricated, and the candor machinery (critics, self-audit) works and says true things. The failures are in acting and disclosing, and each maps to a confirmed defect: the four flagged insertions shipped through **G1** (report-don't-remove default — they were never in M1's audit-demotion path at all); the silent one-provider retrieval collapse and its "verification budget" misdiagnosis flow through **M3** (gate muted by one early result), **M5** (coverage snapshot never reconciled), and **M4** (no disclosure of what was actually checked). Net: a rigorous, well-documented third of an answer — accurate where it checked, incomplete where it didn't, and wrong about its own reasons.

---

## 5. Appendix A — the two decisive checks, re-runnable

Both were first executed in the originating review session (commands not recorded there) and **re-run in this session** at commit `f523225` from the repo root. Commands verbatim; outputs verbatim.

**Probe 1 — M1: the auditor's window is smaller than the panel's.**

```
python3 - <<'PY'
import sys; sys.path.insert(0, '.')
from deepresearch import engine
quote = "the free tier includes a 500 MB database and pauses after seven days of inactivity"
filler_a = "lorem ipsum dolor sit amet " * 480
page = (filler_a[:12500].ljust(12500, "x")) + quote + ("y" * (14000 - 12500 - len(quote)))
assert len(page) == 14000
print("page length:", len(page), "| quote at offset:", page.find(quote))
full = engine.quote_span(page, quote)          # extraction-side check (fetch cap 14000)
audit = engine.quote_span(page[:12000], quote) # auditor's view (refetch cap 12000)
print("extraction view (14000):", full["status"], "offset", full["offset"], "foundFraction", full["foundFraction"])
print("audit view (12000)     :", audit["status"], "offset", audit["offset"], "foundFraction", audit["foundFraction"])
print("panel is told:", engine._quote_line({"quoteCheck": full}).split(" - ")[0])
PY
```

Output:

```
page length: 14000 | quote at offset: 12500
extraction view (14000): located offset 12500 foundFraction 1.0
audit view (12000)     : not-found offset None foundFraction 0.0
panel is told: **Quote located on the page: YES** (100% of it, checked in code, not by a model). Treat the quote as genuine page text and judge only what the claim does with it.
```

**Probe 2 — M3: one cumulative early result disables the gate.**

```
python3 - <<'PY'
import sys; sys.path.insert(0, '.')
from deepresearch import engine
state = {
    "searxng":  {"attempts": 8,  "ok": 0, "fail": 8,  "challenged": 8,  "junk": 0, "results": 0},
    "ddg-html": {"attempts": 40, "ok": 1, "fail": 39, "challenged": 39, "junk": 0, "results": 3},
    "ddg-lite": {"attempts": 6,  "ok": 0, "fail": 6,  "challenged": 6,  "junk": 0, "results": 0},
    "mojeek":   {"attempts": 5,  "ok": 0, "fail": 5,  "challenged": 5,  "junk": 0, "results": 0},
}
engine.search_health = lambda: state
print("39/40 challenged, one ok with 3 results -> _general_web_dead() =", engine._general_web_dead())
state2 = {k: dict(v) for k, v in state.items()}
state2["ddg-html"]["ok"] = 0; state2["ddg-html"]["challenged"] = 40; state2["ddg-html"]["results"] = 0
engine.search_health = lambda: state2
print("same state minus that single early success      -> _general_web_dead() =", engine._general_web_dead())
PY
```

Output:

```
39/40 challenged, one ok with 3 results -> _general_web_dead() = False
same state minus that single early success      -> _general_web_dead() = True
```

---

## 6. Fix these first

Ranked by contribution to the live run's observed failures, then by severity (rubric in §3).

1. **G1 — enforce, or at minimum inline-surface, critic-flagged summary sentences.** The flagship live failure (four flagged insertions, one fabricated, shipped) flows through this default, in both modes; M1's audit gate never saw them.
2. **M3 — recency/rate-based dead-web gate.** The run's defining user-facing failure — a silent one-provider retrieval collapse presented as a budget constraint — passed through a gate one early result permanently muted (Probe 2).
3. **M1 — the audit contract (demote-or-restate non-`supported`; one shared page cap).** The repo's own injected-defect measurement says overstatement ships; Probe 1 shows the demotion layer cannot even see the page tail.
4. **M5 — reconcile the coverage table post-verification.** The stale snapshot is the vehicle by which the report claimed, and mis-diagnosed, its own coverage.
5. **M2 — give the counter lens one real fetch.** Restores genuine 3-lens redundancy for one `web_fetch` per counter-search; cheap relative to the guarantee it repairs.
6. **M4 — unconditional `auditRan` / `verifiedShare` honestLimits.** Makes "how much was actually checked" a stated fact instead of a ≥ 50%-triggered confession, and would have exposed the 100%-Supabase pool.
7. **M6 — Mode A blindness/independence disclosure (or real isolation of the audit).** Every Mode A report carries an untrue headline guarantee; the disclosure fix is one paragraph.
8. **M7 — extract kill/demotion helpers for Mode B.** Removes an instruction that tells windows to run code that does not exist.
9. **M8 — write the full-pool and auditErrors rules into SKILL.md phase 7.** Prevents Mode B from re-creating the 100%-accuracy rubber stamp the engine already measured and fixed.
