# v1.15.0 fix verification — standard-depth run

## 0. Provenance — where every fact comes from

- **Report under test:** `/home/excelsior/.local/share/hermes-agent/research/raw/dr/verify-run.json` (111,828 bytes, mtime 2026-09-20 16:01, owner root). Located by system-wide `find`; every command below was run against this absolute path.
- **Run:** standard depth (`stats.depth = "standard"`), exit 0, engine commit `3f50b9d496f5af381f7fd2783905a39017974d9a` — which is `git rev-parse HEAD` of the working tree whose code is cited below, so the line numbers are that commit's. `pyproject.toml` declares `version = "1.15.0"` at this HEAD; **no git tag points at HEAD** (latest tag is `v1.9.2`).
- **The twelve checks:** their definitions and results were supplied in the ask (the workflow's verification pass). Their raw outputs, beyond the commands and outputs quoted into the results, are not in my possession and are not on disk that I could find.
- **This ask:** I re-ran the report-side checks myself against the file above. Every headline number matched the ask's results (`partial` 2, `restatedToSupported` 5, `citationAccuracy` 93.3, survivors-only 100.0, 28/0/0 supported/unsupported/unreachable, `auditErrors` 0, `demotedBySurvivingPanel` 0, 39/30/9 extracted/verified/dropped, 25/5 confirmed/killed, `generalWebOkRate` 0.677, `auditRefetch` {fresh:30, fellBackToCache:0}, `pageFetchCache` {hits:17, misses:61}, `quoteLocation` {located:29, unverifiable:5, not-found:5}, `fetchVia` {crossref-api:7, http:11}, `singleRater` false, 13 `honestLimits` keys). Facts are tagged **[re-run]** (command in this ask) or **[check]** (ask's result only). I did not run the test suite or any engine code in this ask; code statements come from reading the files at HEAD.

---

## 1. Verdict (3 sentences)

Nine of the ten v1.15.0 fixes named in commit `3f50b9d` hold outright in this real standard-depth run (exit 0; all 30 verified claims audited with 30/30 fresh re-fetches): every disclosed number recomputes exactly — 28 supported + 2 partial = 30 audited rows, 25 confirmed + 5 killed = 30 judged, 39 = 30 verified + 9 dropped, `citationAccuracy` 93.3 = 28/30, survivors-only 100.0 = 25/25 (a partition I re-verified row by row: the 25 confirmed rows are all `supported`, the 5 killed rows are 2 `partial` + 3 `supported`), `generalWebOkRate` 0.677 = 42/62 from `searchHealth` — and the one quote past the old 12000-char audit cap (offset 12545) is `located` with `foundFraction` 1.0. The tenth fix, **restate-or-drop, works in the engine and breaks at the report**: five surviving partial claims were restated and re-audited to supported (`restatedToSupported` = 5), yet `restatedFrom` appears zero times in the report because both serializers omit it — `citation_rows` (`engine.py:1549-1565`, iterating the fact rows) and the quoteAudit builder (`engine.py:3499-3505`, iterating the confirmed claims) — so the five weakened claims sit in the report reading `supported` with no trace of their originals. The fix is additive and two-sided (emit `restatedFrom` in both builders; their in-memory feeds already carry it — `engine.py:3119` on the fact row, `engine.py:3205` on the confirmed claim), and until it lands, v1.15.0 as declared at HEAD carries one open, disclosure-only failure: the verdicts and counts are right, but the before/after of the five weakened claims is invisible.

**Score: 11 of 12 checks pass, 1 fails.**

---

## 2. Check table

Commands below were run against `/home/excelsior/.local/share/hermes-agent/research/raw/dr/verify-run.json` [re-run] unless tagged [check].

| # | Check | Result | Evidence (command → output, or field read) |
|---|-------|--------|--------------------------------------------|
| 1 | `restate-or-drop` | **FAIL** | `grep -o 'restatedFrom' <report> \| wc -l` → **0**; `jq '[paths(objects) as $p \| (getpath($p) \| keys[]) \| select(. == "restatedFrom" or . == "restate")] \| length'` → **0**; `grep -o 'restat[a-z]*' <report> \| sort \| uniq -c` → `1 restated` (inside the `restatedToSupported` key) + `1 restatements` (finding prose). Yet `partial` = 2 and `restatedToSupported` = 5. Full analysis in §4. |
| 2 | `one-page-window` | PASS | `jq '[.quoteAudit[] \| {offset, onPage, foundFraction}] \| sort_by(.offset) \| .[-3:]'` → offsets 6832, **9454**, **12545**, all `located`/`foundFraction 1.0`; the 12545 row (claim "At Neon's April 2024 GA, an HN commenter represented…") is the only quote past the old 12000 audit cap and is `support "supported"` in `citationDetail` **[re-run]**; `.stats.auditRefetch = {fresh:30, fellBackToCache:0}`. The 3 `not-found` statuses are audit-axis rows on killed claims — see §3.2, not window misses. |
| 3 | `auditErrors-accounting` | PASS | `.citationAudit.auditErrors = 0`, reported and disclosed verbatim in `.citationAudit.scope`: "30 of 30 verified claims were audited; 0 call(s) returned nothing after retries and are NOT in the denominator."; `jq '[.citationDetail[].support] \| group_by(.) \| map({(.[0]):length}) \| add'` → `{partial:2, supported:28}`; 28+2+0+0 = 30 = `citationDetail` length = `claimsVerified` **[re-run]**. |
| 4 | `citationAccuracy-arithmetic` | PASS | `28/(28+2+0)*100` = 93.333 → reported 93.3 (1-decimal round); `citationAccuracySurvivorsOnly = 100.0` sits beside it with its note; both `partial` rows' claim texts match `.refuted[]` entries verbatim **[re-run — partition query in §3.1]**, and the 25 confirmed rows are all `supported` → 25/25 = 100.0. |
| 5 | `counter-lens-real` | PASS | `jq '[.refuted[].refutedBy[].lens] \| group_by(.) \| map({(.[0]):length}) \| add'` → `{counter:4, provenance:2, support:5}` = `stats.killsByLens` exactly **[re-run]**; `jq '[.refuted[].refutedBy[] \| select(.lens=="counter") \| has("counterSource")]'` → `[true,true,true,true]` **[re-run]**; counterSource values are `news.ycombinator.com/item?id=26637929`, `kuberns.com/blogs/railway-free-tier/`, `supabase.com/pricing` (corroborating `supabase.com/docs/guides/platform/backups`), `docs.railway.com/reference/pricing/plans` (corroborating `docs.railway.com/pricing/free-trial`) — the four named URLs' evidence fields embed quoted page text, and the five non-main URLs are absent from the 18-item `sources[]` (verified per-URL with `jq -e '[.sources[].url] \| any(test($u))'` → false for each) **[re-run]**. The fetch itself is code-verified at `engine.py:2530-2537` (`web_fetch(hits[0], cap=8000)`, 6000 chars into the counter block). |
| 6 | `importance-first-pool` | PASS | `.honestLimits.evidenceChecked` = "30 of 39 extracted claims were verified (9 unchecked, ranked out of the panel budget by importance then tier). Unchecked is not refuted…" reconciles: 39 = 30 + 9 (`claimsExtracted/claimsVerified/claimsDroppedBeforeVerify`), 30 = 25 + 5, `refuted` length 5 **[re-run]**; cited-index union (see §7) stays inside 0..24; `.answerFirst` independently states "Material disclosure: 23% of extracted claims (9 of 39) were never verified…" **[re-run]**; the "importance then tier" wording matches the sort at `engine.py:2359-2368` [check]. |
| 7 | `post-verification-coverage` | PASS | `jq -r '.coverage[].status'` → 5× `partial`, 3× `unanswered`, zero `answered` **[re-run]**; `grep -c 'claims mapping here died'` → 0 **[re-run]**; every sub-question with evidence retains surviving confirmed claims (e.g. sq2/sq3 rest on confirmed [0]/[8] after the Reddit-OP pause claim died — `.refuted[3]` vs findings[2] vote "3-0 on [0] and [8]; 2-1 on [14]") [check]. Note-text residuals: §5. |
| 8 | `kill-rule-min-2-votes` | PASS | `jq -c '[.refuted[] \| {killedBy, vote, refuteCount: (.refutedBy\|length)}]'` → killedBy `support+counter` ×3, `support+provenance`, `support+counter+provenance`; votes `1-2`×4, `0-3`; refuteCounts `[2,2,2,2,3]` — no 1-vote kill **[re-run]**; rule at `engine.py:2499-2508` (`is_refuted = refuted >= required`, `REFUTATIONS_REQUIRED = 2` at `engine.py:75`); citation-audit demotion branch unused (`demotedBySurvivingPanel = 0`, `unsupported = 0`) **[re-run]**. |
| 9 | general-web rate agrees with `searchDegraded`/`searchHealth` | PASS | `python3 -c 'print(round((36+0+0+6)/(41+7+7+7),3))'` → 0.677 = reported `generalWebOkRate` (from `searchHealth`: searxng 36/41, mojeek 6/7, ddg-html 0/7, ddg-lite 0/7) **[re-run]**; threshold `att > 0 and ok/att < 0.2` at `engine.py:3703-3710` over `GENERAL_WEB` (`engine.py:3695`) → not degraded; `.searchDegraded = false` agrees. (The field lives at the report top level, not under `stats` — §5.) |
| 10 | audit at standard depth (no `citationAuditOff`; metrics present) | PASS | `jq '.honestLimits \| has("citationAuditOff")'` → false; the 13 keys are listed in §0 **[re-run]**; audit metrics populated: `citationAccuracy` 93.3, `auditRefetch {fresh:30, fellBackToCache:0}`, `quoteAudit` length 25 = `stats.confirmed` 25 with onPage census `{located:21, unverifiable:4}` **[re-run]**; `contract/depths.json` → `depths.standard.audit = true` (read in this ask); the key is added only when audit is off (`engine.py:1874-1878`). |
| 11 | `singleRater` false on harness transport | PASS | `jq '{singleRater, transport: .stats.transport, depth: .stats.depth}'` → `{singleRater: false, transport: "session", depth: "standard"}`; `jq '.honestLimits \| has("singleRater")'` → false **[re-run]**; scheme rule read at `providers.py:311-312` (`"stdio" if argv == ["<stdio>"] else "session"`); report side at `engine.py:2807` and `engine.py:1880-1886`. |
| 12 | `honestLimits` carries `evidenceChecked` and `searchCoverage`, reconcilable | PASS | `jq '.honestLimits \| has("evidenceChecked")'` → true, `has("searchCoverage")` → true **[re-run]**; evidenceChecked reconciliation as row 6; `searchDegraded = false` holds under both the prose's all-or-nothing reading and the live <0.2 rate test. The prose/rule divergence itself is a residual defect — §5. |

---

## 3. Two reconciliations the score depends on

### 3.1 How `partial = 2` and `restatedToSupported = 5` coexist

They count different things at different times, and the code pins this down:

- **The gate** (`engine.py:3103`, read in this ask): `if f.get("support") == "partial" and c.get("survives")` — restatement is attempted **only for partial verdicts on panel-surviving claims**. Killed claims are never restated.
- **The swap** (`engine.py:3197-3210`, read in this ask): when the re-audit of a restated claim comes back `supported`, the weakened text replaces the confirmed claim's text, `c["restatedFrom"]` records the original, and `restated += 1` → `fact_metrics["restatedToSupported"]`. So **`restatedToSupported` = 5 means five surviving claims were partial mid-audit, were restated, re-audited supported, and swapped in.** After the swap their rows read `supported`.
- **The 2 rows still reading `partial` are partials on panel-killed claims**, which the gate never touches. Verified by direct partition [re-run]:

```
jq -c '[.citationDetail[] as $r | {claim: $r.claim, support: $r.support,
      killed: ([.refuted[].claim] | any(. == $r.claim))}]
      | group_by(.killed) | map({killed: .[0].killed, n: length,
      supports: ([.[].support] | group_by(.) | map({(.[0]): length}) | add)})'
→ [{"killed":false,"n":25,"supports":{"supported":25}},
   {"killed":true, "n":5, "supports":{"partial":2,"supported":3}}]
```

The two partial rows' texts ("A December 2025 commenter reported that after six months hosting a Shopify app…" on the r/node Reddit thread, and "Database backups are not downloadable for Supabase Free Plan…" on supabase.com/docs) match `.refuted[]` entries 1 and 2 verbatim [re-run].

**Stated outright, the fact the failure's severity rests on:** the 5 restated claims are surviving claims among the 25 confirmed; their final `citationDetail` and `quoteAudit` rows read `supported` and carry the **weakened** text (the fact row's `claim` is the re-audited text — `engine.py:3117-3121`), and because `restatedFrom` is not serialized, nothing in the report distinguishes them from claims that were supported outright, and their originals are unrecoverable from the report. Partition: 30 = 25 confirmed (all supported) + 5 killed (3 supported + 2 partial) — now verified, not inferred.

### 3.2 The three `not-found` rows vs the 25-row quoteAudit

The premise that "3 of the 25 quoteAudit rows have quotes not found on page" is false — the two tables measure quote location on **different axes over different pools**:

- **`quoteAudit`** (25 rows, the confirmed pool): `onPage` comes from the extractor's own quote checked in code against the fetched page (`c["quoteCheck"]`, `engine.py:3499-3505`). Census [re-run]: `{located: 21, unverifiable: 4}` — **zero not-found**. The 4 unverifiable rows are 2 on supabase.com/pricing and 2 on github.com/supabase/supabase [re-run].
- **`citationDetail`** (30 rows, every verified claim): `locatedQuoteOnPage` is the **auditor's** `locatedQuote` checked against the fresh re-fetch (`f["locatedQuoteCheck"]`, `engine.py:1564`). Census [re-run]: `{located: 23, located-elided: 2, not-found: 3, partial: 1, unverifiable: 1}`.
- **`stats.quoteLocation`** (`{located:29, unverifiable:5, not-found:5}`) is the extraction-stage census over all 39 extracted claims — a third axis again.

**The 3 audit-axis not-founds [re-run]:** all on one URL (`reddit.com/r/node/comments/1fbpevm/railwayapp_free_plan_usage_advice_or_any/`), all belonging to **killed** claims (the partition query above), with support values **1 `partial` + 2 `supported`**. Each row's own `reasoning` field attributes the not-found to the fetch path, e.g. "The live fetch of the URL returned only a 'Reddit' shell (direct extraction failed), but the thread's actual content was retrievable via a search-backend crawl…" and "The live URL returns only a JavaScript shell ('Reddit') to non-browser fetchers…". That is the report's own account — no fetch-and-compare was run by the checks or by me, so "rendering failure" is the auditor's stated cause, not an independently established one.

**Is not-found-but-supported intended?** What the code settles: demotion keys on the **support** axis only — `demotion_set` (`engine.py:2481-2495`, read in this ask) demotes `unsupported` always, and `partial` only when a restatement was re-audited and still failed; a `locatedQuoteOnPage` not-found enters no rule. Consistently, this run's 2 not-found+supported rows kept `support "supported"`, and `demotedBySurvivingPanel = 0`. Whether shell pages *should* weigh on location verdicts is a design question this material cannot decide; mechanically, the axes are independent by construction.

---

## 4. The one failure — `restate-or-drop`

**The normative source, verbatim** (commit `3f50b9d` message, first bullet, obtained via `git show -s --format=%B HEAD` in this ask):

> "Restate-or-drop: the audit's PARTIAL verdict no longer leaves overstated claims fully in the report. A partial SURVIVOR is restated to what the auditor's locatedQuote supports (p_restate), re-audited, and the re-audit verdict decides: supported swaps the weakened claim in (restatedFrom preserves the original); partial/unsupported again demotes like unsupported."

**The precise obligation.** The commit scopes restatement to partials **on surviving claims**. The check's own expectation added an alternative: "or a defensible zero when no partials occurred" — meaning: had `citationAudit.partial` been 0, `restatedToSupported = 0` with no `restatedFrom` anywhere would have been consistent. That is the "defensible-zero branch," and it is unavailable here because `partial = 2`. Note the trigger nuance the check glossed: the two *visible* partials are killed-claim rows (§3.1), so the surviving-partial trigger is not directly visible in the final counts — but it does not need to be, because `restatedToSupported = 5` is itself the count of survivor restatements that swapped in. The obligation to preserve five originals stands on that field alone.

**Observed [re-run].** `restatedToSupported = 5`, `partial = 2`, and `restatedFrom` occurs **0 times** in the report (`grep -o 'restatedFrom' | wc -l` → 0; recursive jq key scan → 0). `citationDetail` rows carry exactly `[claim, url, support, reasoning, locatedQuote, locatedQuoteOnPage]`; `quoteAudit` rows exactly `[claim, url, quote, onPage, foundFraction, offset]`; findings exactly `[citationCheck, claim, confidence, evidence, factInferenceAssumption, sourceTier, sources, vote]` [check; key sets re-confirmed for the first two in this ask]. The originals of the five weakened claims appear nowhere; a reader sees the count 5 and cannot see what changed (§3.1).

**Root cause — both feed paths, read in this ask.** The engine sets the field at two in-memory sites, and each report builder draws from a different one:

| Serializer | Iterates | In-memory feed that already carries `restatedFrom` |
|---|---|---|
| `citation_rows` (`engine.py:1549-1565`) | `fact_by.values()` — the audit's fact rows | the fact-row return at `engine.py:3117-3121` (`restatedFrom=c["claim"]`, plus an `restate` metadata dict; the site the check cited as `engine.py:3119`) |
| quoteAudit builder (`engine.py:3499-3505`) | `confirmed` — the post-swap confirmed claims | the swap loop at `engine.py:3197-3210`, whose `c["restatedFrom"] = f["restatedFrom"]` assignment is the site the check cited as `engine.py:3205`, under the comment "its original preserved in restatedFrom so the report can show what changed" (`engine.py:3197-3199`) |

Neither builder emits the field, so the promise is kept in memory and dropped at both report exits.

**Smallest fix (two lines of intent, one per builder).** Add the field to each emitted dict, passing through what the feed already carries:
- in `citation_rows`: `"restatedFrom": webtext(f.get("restatedFrom", ""), 300)` alongside `claim`;
- in the quoteAudit builder: `"restatedFrom": webtext(c.get("restatedFrom", ""), 300)` alongside `claim`.

No engine-logic change is involved — the values exist at both feeds before serialization. This grounds the claim the previous draft made loosely: each builder has its *own* feed site (3119 for `citation_rows`, 3205 for quoteAudit), so "same pass-through" means one added line per builder. On the commit's own wording ("the report can show what changed"), the two row builders are sufficient; the findings serializer needs nothing.

**Severity and disposition.** Disclosure-only: the weakening itself happened, is counted (`restatedToSupported` = 5), and all 25 confirmed claims' final texts were audited `supported` — the verdict arithmetic is unaffected; what is lost is the before/after of five claims. **v1.15.0 state:** `pyproject.toml` declares 1.15.0 at HEAD `3f50b9d`; no git tag points at HEAD; whether it ships with this open is the release owner's call — the verification verdict is simply "one open failure." **What confirms the fix once applied:** re-run standard depth, then (a) `grep -o 'restatedFrom' <report> | wc -l` must equal 2 × `citationAudit.restatedToSupported` (both tables emit it); (b) `jq '[.citationDetail[] \| select(has("restatedFrom"))] \| length'` must equal `.citationAudit.restatedToSupported`; (c) `jq '[.quoteAudit[] \| select(has("restatedFrom")) \| .restatedFrom != .claim] \| all'` must be true (the preserved original differs from the weakened text). Durable: a conformance gate in `tests/test_pipeline.py` asserting both builders emit `restatedFrom` when their input row carries it — the repo's established pattern (e.g. the `post_verify_coverage` gates at `tests/test_pipeline.py:2925-2932`, read in this ask).

---

## 5. Residual defects observed in this run's report, with disposition

These are real defects in the output, observed and given a verdict; they are not things the run "could not exercise."

1. **Three coverage notes carry stale pre-verification framing** (conservative direction — they understate what was confirmed). Note texts re-read in this ask [re-run]:
   - `coverage[0]`: "…the per-database/branch/project/volume split and the at-or-above-2GB test are entirely unsourced for Neon, Supabase, and Railway" — while confirmed claims exist on supabase.com/pricing (e.g. the quoteAudit rows "Supabase's free tier compute consists of shared CPU and 500 MB RAM", "Supabase's free tier includes 5 GB of egress") [check's reading: confirmed [1] "500 MB per project"].
   - `coverage[2]`: "Supabase's 7-day pause is known only from the original poster's Reddit comment" — that exact claim was killed (`.refuted[3]`, `support+provenance`), and official-page claims [0]/[8] confirmed the pause [check].
   - `coverage[6]`: "Zero evidence gathered on Fly.io, Render, …" — despite confirmed [6],[11] (findings[4]: "3-0 on both [6] and [11]") [check].
   **Cause/scope:** the v1.15.0 fix (`post_verify_coverage`, `engine.py:2323-2350`) reconciles row **status** only; note text is untouched. **Disposition:** open report-quality defect, conservative direction, not claimed fixed by the commit; smallest remedy is a separate change reconciling note text after kills. No code was changed in this verification.
2. **`honestLimits.searchCoverage` prose describes a superseded rule.** The prose (read verbatim at `engine.py:1966-1970` and in the report) says `searchDegraded` "is true when every general-web backend returned 0 results for the whole run" — the all-or-nothing test — while the live rule is `att > 0 and ok/att < 0.2` (`engine.py:3703-3710`, whose comment says it replaced that test). Also, the prose points at "stats.searchDegraded" but the field lives at the report top level (`.stats.searchDegraded` is null; `.searchDegraded` is false) [re-run]. **Disposition:** stale-doc defect, no effect on this run's verdict (false under both rules); not fixed here.
3. **The failure of §4** — disposition there.

---

## 6. What this run could not exercise

- **The old-cap boundary, once only.** Exactly one quote past the old 12000-char audit cap occurred (offset 12545). The 9454 row ("An HN commenter alleged Neon suffered 12 significant outages…", `located`, `foundFraction 1.0` [re-run]) sits below 12000, so it was locatable under either cap — it never depended on the fix. No run with multiple late-page quotes.
- **Audit degradation paths.** `auditErrors = 0` and `auditRefetch = {fresh:30, fellBackToCache:0}` — neither the audit-call-returns-nothing path (exclusion from the denominator plus reporting) nor the cache-fallback path fired.
- **Citation-audit demotion, both branches.** `demotedBySurvivingPanel = 0`, `unsupported = 0` — no survivor was demoted; and since all 5 restatements came back supported, `demotion_set`'s partial-after-failed-restate branch (`engine.py:2490-2493`) and its partial-with-no-re-audit guard never fired on live data.
- **The `killed-in-verification` flip.** Zero rows carry the status or the "claims mapping here died in the panel or audit" marker [re-run]; no sub-question that read `answered` lost all its claims. Unit coverage exists (`tests/test_pipeline.py:2931-2932`, read in this ask) but I did not run the suite in this ask.
- **Too-few-verdicts.** `unverifiedCount = 0` — the UNVERIFIED path never fired.
- **Degraded search.** `searchDegraded = false` throughout (0.677 ≥ 0.2).
- **stdio / Mode A.** `transport = "session"` — the `singleRater = true` and `honestLimits.singleRater` branches (`engine.py:2807`, `engine.py:1880-1886`) untested live; likewise `citationAuditOff` (audit was on at standard depth).
- **A per-URL counter-fetch ledger.** Correcting the previous draft's arithmetic [re-run]: `pageFetchCache {hits: 17, misses: 61}` is **78 cache accesses, not 78 fetches** — the 17 hits were served from cache (106,036 chars; hitRate 0.218), the fetch count is the 61 misses. Known demand accounts for 41 of them (30 audit re-fetches, forced fresh; 11 `http` main sources), leaving 20 misses for counter pages and everything else (search-backend crawls, rescues) — the counter lens allows up to 30 fetch attempts (`engine.py:2528-2531`, one per verified claim when the search returns hits), so the numbers are consistent with it but do not measure it; `fetchVia` censuses only the 18 main sources and the crossref-api path's cache use is not visible in the report. The direct evidence of counter-page reading remains the quoted text and URLs in the `refutedBy` fields (§2 row 5) — no fetch-and-compare was performed by the checks or by me.
- **Verbatimness of quoted page text, independently.** Both the counter-evidence quotes and the auditors' `locatedQuote`s were read as strings in report fields; nothing in this verification re-fetched a page and diffed a quote against it.

---

## 7. Notation and the cited-index detail

- **`refuted[].vote` "a-b"**: a = valid panel verdicts **not** refuting, b = refuting, over the 3 lenses; a kill requires b ≥ `REFUTATIONS_REQUIRED` = 2 (`engine.py:75`; `tally_verdicts` at `engine.py:2499-2508`; the "a-b" format is built at the tally site, `engine.py:2576-2578`). This run's kills: `1-2` ×4, `0-3` ×1, with `refutedBy` lengths `[2,2,2,2,3]` [re-run].
- **Offsets and caps**: `offset` is where the quote begins in the normalized fetched page. `PAGE_CAP = 14000` (chars fetched — sweep **and** the audit's re-fetch; `engine.py:83-84`), `PAGE_VIEW = 13000` (chars any prompt is shown; `engine.py:84-85`; audit prompt at `engine.py:1650`, fresh re-fetch at `engine.py:3072`). The old audit cap was 12000; `engine.py:81-82` records the reproduced defect: "a quote at offset 12500 checks located at cap 14000 and not-found at cap 12000."
- **"The clean 9454 case"** (§6): the second-deepest quote in `quoteAudit` — offset 9454, `located`, `foundFraction 1.0` — locatable under both the old and new caps, hence independent of the fix.
- **`ok/att < 0.2`**: `_gw_dead_from_health` (`engine.py:3703-3710`) — general-web backends (`searxng, ddg-html, ddg-lite, mojeek`, `engine.py:3695`) answered under a fifth of their attempts, with attempts > 0.
- **`scope`**: the `citationAudit.scope` field, quoted verbatim in table row 3.
- **`answerFirst`**: a top-level report field (the pre-synthesis answer draft); its disclosure sentence is quoted in table row 6 — it states the same 9-of-39 unchecked share as `honestLimits.evidenceChecked`, independently.
- **`[n]` indices** (votes, `claimsCited`, critique prose): claim indices into the run's claim ordering. **Cited-index recount [re-run]** — union of `findings[].vote`, `hypothesisVerdicts[].claimsCited` (`[[1,0,8],[7,12,21,22,24],[3,15,18],[1,3,15,18,6,11]]`), and bracketed indices in `processCritique.coverageGaps`/`untraceableStatements`: {0,1,2,3,4,5,6,7,8,9,10,11,12,14,15,16,18,19,20,21,22,24} — 22 of the 25 confirmed slots; **uncited by these structured fields: {13, 17, 23}**. Caveats, stated not smoothed: the raw file contains "[13]" ×3 and "[17]" ×1 in prose fields I did not attribute, so the uncited set could be smaller if those are claim citations ("[23]" appears nowhere); and the ask's check paraphrased the union as "{0..12, 15..22, 24}", which differs at the edges from this recount (it includes 17 and omits 14; the recount finds 14 cited in the vote string "2-1 on [14]"). **Killed claims' indices are published nowhere** — `refuted` rows carry exactly `[claim, contradictedBy, killedBy, refutedBy, source, vote, why]` [re-run] — so "cites only confirmed indices" is established by range (no citation falls outside 0..24 under either set), not by per-kill exclusion.
