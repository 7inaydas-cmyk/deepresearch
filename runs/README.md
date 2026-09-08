# Recorded runs

Raw output, kept so every number in the README can be checked rather than taken on
trust. Nothing here is cherry-picked; the failed and blocked runs are in here too.

## Two regimes, and they are not comparable

Everything with a `v2-` prefix was produced **after** 2026-09-06, with a local SearXNG
serving general-web results and with five instrument bugs fixed. Everything without the
prefix predates both, and is **superseded**.

The old runs are kept, not deleted, because they are the honest record of what the tool
did in the degraded regime, and because the before/after is itself a measurement. But
they should not be quoted as current numbers:

- **Search was scholarly-only.** All four general-web backends returned zero results on
  every one of them. Coverage gaps in those reports are a search artefact, not evidence
  that nothing exists. On the one question run under both regimes, sources went from 14
  to 26 and claims from 9 to 33.
- **Calibration ran on a biased sample.** The sampler took the first N of a rank-ordered
  list, so the subset was the strongest claims and skewed heavily toward survivors.
- **The strike policy never fired**, so `struckFromSummary` is empty in every one of
  them whatever the policy says.
- **`--calibrate` / `--sample-dropped` were reachable only by CLI flag.** A run that set
  the environment variables instead reported `calibration: null` with no explanation.
- Runs older than 2026-09-06 also have `hypothesisVerdicts: null`, because nothing after
  the framing phase read the contract yet.

## What the current regime measured

Six runs, `--calibrate 30 --sample-dropped 10`, 2026-09-06/07. Regenerate with
`python3 tools/compare_regimes.py`.

| Run | Kill rate | Citation acc | kappa | n | Gate |
|---|---|---|---|---|---|
| `v2-minimum-wage-employment` | 37% | 85.7% | 0.86 | 30 | **calibrated** |
| `v2-mammography-forties` | 17% | 82.9% | 0.71 | 30 | **calibrated** * |
| `v2-standing-desks` | 11% | 80.0% | 0.53 | 30 | usable but noisy |
| `v2-tdd-defect-rates` | 30% | 38.1% | 1.00 | 27 | underpowered |
| `v2-ai-water-per-query` | 52% | 61.9% | 0.79 | 21 | underpowered |
| `v2-nudge-publication-bias` | 17% | 90.0% | 0.75 | 12 | underpowered |

\* `v2-mammography-forties` hit a bug: synthesis failed, and the fallback return path
discarded the calibration and dropped-claim blocks that had already been computed and
logged. Both were recovered from `v2-mammography-forties.log` and re-inserted, flagged with
`recoveredFrom`. The per-lens table was not recoverable, so that `calibrated` verdict cannot
be re-checked against the per-lens precondition. The bug is fixed; no other run is affected.

`v2-nudge-publication-bias` ran while SearXNG had `qwant` enabled, which was returning
**fabricated** results — nonsense domains with gibberish titles, interleaved 1:1 with real
ones. Nothing fabricated was cited (the source picker rejected all of it), but it cost 11 of
15 source-picks and the run finished with 12 verified claims instead of 30. Treat its
numbers as compromised. Qwant is disabled from `v2-minimum-wage-employment` onward.

## Prompt A/B: the audit's section order

`ab-audit-prompt-order-2026-09-08.json`. Anthropic's prompt cache covers a *prefix*, so
caching the audit's ~3000-token page block requires moving it above the statement. That
is a change to the prompt behind the headline number, so it was measured before it
shipped rather than argued about.

30 identical `(claim, url, page)` triples from `v3-nudge-contract.json`, replayed through
the current prompt **twice** — the control for how much the judge disagrees with itself —
and then through the reordered prompt.

| comparison | verdicts that differ | n |
|---|---|---|
| current vs current (control) | **0.000** | 30 |
| current vs reordered | **0.200** | 30 |

Zero self-disagreement, so all six changed verdicts are attributable to the reorder. They
ran both ways (3 `partial`→`supported`, 2 `supported`→`partial`, 1 `partial`→`unreachable`)
and the net moved headline citation accuracy 77.8% → 84.6%. The reorder was reverted and
prompt caching refused; see `docs/adr/0003-no-prompt-caching.md`.

**What this cannot show:** n=30 on one question detects a shift of roughly this size. A
smaller systematic drift would not clear this sample.

## Production check: the page cache and the token census

`v4-4day-pagecache.json`, a standard run on the current regime.

| what | result |
|---|---|
| `stats.pageFetchCache` | 19 hits / 12 misses, **61.3% hit rate**, 97,280 chars served from memory |
| `stats.usageUnrecorded` | 3 fields the build does not name, **2 of them unpredicted** |

The cache result is the audit re-reading pages the sweep already pulled: 19 network
round-trips that no longer happen. The census result is the more interesting one — it
reported `cache_creation.ephemeral_5m_input_tokens` and
`cache_creation.ephemeral_1h_input_tokens` alongside the expected
`output_tokens_details.thinking_tokens`. The API breaks cache creation down by TTL under a
*nested* object, which is not what either the external review or this change predicted. A
hardcoded list of missing fields would have shipped looking correct and still been short by
two.

**Caveat on this file:** it was produced mid-change. The process loaded the engine before
`honestLimits.evidenceBase` was added, so this report does not carry that field. Everything
else in it is current-regime.

## Are the quotes real? (2026-09-08)

`quote-location-2026-09-08.json`. Every Claim carries a verbatim quote, and until this
date nothing checked it: "VERBATIM" appeared in three prompts and in no code. The
quote-support lens was even instructed to "refute if the quote is a paraphrase rather
than verbatim page text" while never being shown the page.

The real extractor was run over real pages and every quote scored against the exact text
the extractor saw.

| measured on | quotes | on page |
|---|---|---|
| published claims, two live runs, after all matcher fixes | 46 | **97.8%** (45/46) |
| the same 46, as first recorded | 46 | 87.0% |

**The gap between those two rows was the checker, not the extractor.** Three separate
bugs in the matcher each manufactured false accusations, and each was found by measuring
rather than reasoning:

1. Exact-match-or-nothing scoring: one differing character in a quote's tail collapsed
   the score to 0.0, and a PMC quote that was on the page IN FULL read `not-found`.
2. PDF line-break hyphenation: real quotes carried `con- clusive`, `standard- ized`,
   `fol- lowing`, and the de-hyphenation rule only fired on a newline the reader had
   already collapsed to a space.
3. Normalisation asymmetry, the worst of the three: `webtext` DELETES every
   double-quote lookalike before the page reaches the model, while `norm_quote` MAPPED
   them. On any page carrying quotation marks - most research prose - a quote
   faithfully reproducing what the model was shown scored `not-found` at fraction 0.0.

Two things came out of it that were not the point of the exercise:

**Four fabricated quotes, from one poisoned source.** `digamoo.free.fr/neumark1994.pdf`
uses a font encoding our extractor cannot map, so it yielded control characters — 13%
letters, zero English stopwords. The old guard counted "words over 3 characters" and let
it through. The model, handed 14,000 characters of that, returned four fluent invented
quotes about employment elasticities. The quote check caught all four; a `prose gate` now
refuses the page outright.

**A false accusation of our own making.** Our PDF reader renders the `fi` ligature as a
SPACE, so nber.org/w32902 reads `magni es` where the paper says `magnifies`. The model
quoted our text faithfully as `magnies`, and an exact-match scorer called that quote
defective. The scorer now also compares ignoring whitespace. An earlier version of the
scorer had a worse form of the same fault: one differing character in a quote's tail
collapsed the score to 0.0, and it reported a PMC quote that was on the page *in full* as
`not-found`. That is the failure mode a checker like this must not have — it manufactures
the fabrication signal it exists to detect — and it is why the scorer is graded and
windowed rather than exact-match.

### Live, end to end (`v5-4day-quotes.json`)

The same question as `v4-4day-pagecache.json`, with quote location in the pipeline.

| | v4 | v5 |
|---|---|---|
| quotes located on page | not checked | **97%** (65 located, 1 partial, 1 unverifiable) |
| citation accuracy (pool) | 66.7% | **83.3%** |
| citation accuracy (survivors, market-comparable) | 75.0% | **91.3%** |
| unsupported / unreachable | 1 / 1 | **0 / 0** |
| agent calls | 172 | **159** |
| wall clock | — | **391.7s**, against a 10.6-minute median before this week |
| page-cache hit rate | 61.3% | 58.8% |

`quoteAudit` carries all 23 published claims with their quote, status, fraction and
character offset. `citationDetail` carries `locatedQuote` on all 30 rows - the auditor's
own verbatim pull, which was previously computed on every call and read by nothing.

Two caveats on this table. One run each, on one question, so these are observations and
not a benchmark. And the survivors-only 91.3% is the number to compare with published
commercial figures (Perplexity 90.2%, Gemini 81.4%, OpenAI 78.0%) because it is measured
their way; the 83.3% is ours, on a harsher denominator.

### The archive fallback, live (`v5-nudge-wayback.json`)

A question whose sources include a Cloudflare-blocked publisher.

    fetchVia: {crossref-api: 12, http: 7, failed: 2, wayback: 1, pdf: 1, crossref-fallback: 2}

`pnas.org/content/pnas/119/1/e2107346118.full.pdf` was read from the Internet Archive's
raw capture and graded T2. Without the fallback it would have been a third `failed`.
Citation accuracy 73.3% pooled / 83.3% survivors-only; 165 calls, 442.9s.

The on-page rate on this run first read **78.3%** and re-scores at **95.7%** after the
matcher fixes; `v5-4day-quotes.json` re-scores at 100%. The gap was ours rather than the
extractor's: four published
quotes carried PDF line-break hyphenation - `con- clusive`, `standard- ized`,
`fol- lowing`. The de-hyphenation rule only fired on a newline, and the reader collapses
the newline to a space before the matcher sees it. Fixed, and the same 23 quotes
re-scored at **87.0%** with nothing else changed.

**The on-page rate is a lower bound on quote fidelity.** What still reads `partial` on
PDF sources is largely our own extraction damage: the reader drops the `fi` ligature, so
a page reads `signicant` and a faithful quote scores short. Whitespace and hyphenation
are normalised away; characters dropped inside a word are not, and could not be without
making the matcher too loose to mean anything.

## The strike fires (`v6-strike-fires.json`, DR_UNTRACEABLE=strike)

`policy: strike, untraceable: 9, struck: 0` was the recorded state of this mechanism on
every run it had ever run, and "strike never fires" survived three external reviews as
an open finding. The cause was not the critic and not the policy. The critic is shown
`webtext(summary, 3000)` - quote lookalikes DELETED, whitespace collapsed - and the
match was a plain substring test against the RAW summary, which fails on any summary
carrying a quotation mark.

    policy            : strike
    untraceableCount  : 8
    struckFromSummary : 2      <- first time above zero

Same run, with the other review fixes in:

| | value |
|---|---|
| quotes located on page | **97.1%** (32 located + 1 elided of 34) |
| citation accuracy | **90.0%** pooled / **90.9%** survivors-only |
| refuted rows naming a contradicting source | **7** — a field demanded on every counter-lens call and previously read by nothing |
| agent calls / wall | 156 / 432.7s |

One run on one question. The `struck: 2` is the load-bearing number here, not the
accuracy: it is a mechanism moving off zero for the first time.

## An unread page is not an unsupported claim (2026-09-08)

Hermes filed this as waste: the audit spends a model call on an empty page. Testing it
found the efficiency finding sitting on top of a correctness one. Same claim, same URL,
12 audit calls each:

| what the auditor was shown | verdict |
|---|---|
| an EMPTY page | `unreachable` **12/12** — correct, so the call buys nothing |
| an ABSTRACT STUB | `unsupported` **12/12** — wrong, and `unsupported` is the only verdict that demotes a claim the panel already passed |

`if not text.strip()` catches the case the model already handles perfectly and misses
the case it gets wrong every time. The real question is not *empty versus non-empty* but
**did we read the page this claim cites**, which `_fetch_meta[url]["via"]` had recorded
all along and no judgement ever consulted.

**A/B before shipping the prompt change**, 6 reps per cell, control = the same prompt run
twice:

| claim against an abstract | control ×2 | with the note |
|---|---|---|
| detail an abstract cannot carry | `unsupported` 6/6 | **`unreachable` 6/6** |
| genuinely not supported | `unsupported` 6/6 | `unsupported` 6/6 |
| the abstract's own finding | `supported` 6/6 | `supported` 6/6 |

Zero control noise, and only the intended verdict moved — so it is not a blanket escape
hatch.

**Exposure, honestly:** across 12 recorded runs there are 4 abstract-only sources out of
226, and 1 of 10 `unsupported` verdicts landed on one. A latent defect with one observed
false kill, not a systemic one — and the archive fallback added the same day shrinks it
further by preferring archived full text over the abstract.

**The same note on the provenance LENS changed nothing**, across 4 claim types and both
provenance kinds at 6 reps each, against a zero-noise control. It ships because
withholding true information from the lens whose subject it is cannot be defended, and
it reuses a seam the audit already needed — not because it was shown to help. Recorded
so nobody later assumes it is load-bearing.

### What the live run actually showed (`v7-provenance.json`)

Best headline numbers recorded — 86.2% pooled / 88.9% survivors citation accuracy, 98.7%
of quotes located on their page, 0 `unsupported`, 163 calls. But the two things this run
was launched to verify came back mixed, and the honest reading matters more than the
numbers:

**The code short-circuit did not fire — 0 times — and that is not a defect.** A source
that fails to fetch produces no claims, so no claim cites it and the audit never sees it.
And since `web_fetch` began caching per URL, the audit reuses the sweep's text instead of
refetching, so a transient audit-time failure cannot happen either. The page cache had
already removed most of the condition Hermes measured. The short-circuit stays as defence
in depth, but it is now a rarely-reachable path, and this run did not exercise it.

**The abstract path is verified by the A/B, not by this run.** One claim was cited to an
abstract-only source and came back `partial` — which does not demote, so the claim
survived, consistent with the fix. But n=1, and `partial` is not the `unreachable` the
controlled experiment produced 6 times out of 6. The controlled A/B is the evidence here;
this run is only compatible with it.

**The archive fallback carried the run.** 5 sources read via `wayback` produced 7
`supported` verdicts, including PNAS and SAGE — publishers that block a direct fetch.
Without it those would have been abstracts or nothing.

## Hypothesis matching, and two false stamps on the way (2026-09-08)

`v10-hypothesis-matching.json`. Stamping each `hypothesisVerdict` with whether its
hypothesis was pre-registered took three attempts, and the first two each put a FALSE
statement in a report - the exact defect the stamp exists to prevent. Both were green in
CI while a live run showed the report lying, which is why this one was calibrated on real
pairs instead of reasoned about.

| attempt | method | live result |
|---|---|---|
| 1 | truncate BOTH sides to 80 chars, test containment | **4 of 4** pre-registered hypotheses stamped post-hoc |
| 2 | strip the `H1:` label, 60-character probe | **2 of 4** stamped post-hoc |
| 3 | content-word overlap, threshold 0.6 | correct on all pairs across three runs |

Attempt 1 cannot work: synthesis relabels each hypothesis `H1: `, and a four-character
prefix shifts the alignment so containment never holds. Attempt 2 fails because the model
rewords mid-sentence - `"The debate is largely a definitional/measurement artifact"` is
56 characters of exact agreement before diverging, so a 60-character probe missed it.

Calibration, over 8 true pairs and 24 cross pairs from two runs:

    true pairs (same hypothesis, reworded) : 0.95 - 1.00
    cross pairs (different hypotheses)     : max 0.22

**And the third run widened that.** Fitted to nothing, it matched all four correctly - but
two scored **0.82**, against a calibration whose lowest true pair was 0.95. The threshold
stands, since 0.82 clears 0.6 and the highest cross pair anywhere is 0.22, but the honest
margin is ~0.22 rather than the ~0.35 the first eight pairs implied.

## The files

| Prefix | What it is |
|---|---|
| `v2-*` | Current regime: SearXNG on, all five fixes in, `--calibrate 30 --sample-dropped 10`. |
| `probes-*` | Injected-defect probe results for the citation auditor and the process critic. |
| `ab-*` | Prompt A/B experiments: identical inputs replayed through two prompt shapes, with a same-prompt control for the judge's own noise. |
| `v4-*` | Current regime plus the per-URL page cache and the full token census. |
| `calibration-*` | Panel reliability runs, superseded — the first two are the ones the gate amendment was written against. |
| `*-BLOCKED-*` | A run that died on a server-side credential revocation. Kept because it is why `preflight()` exists. |
| everything else | Superseded regime. See above. |
