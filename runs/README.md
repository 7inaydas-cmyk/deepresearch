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

## The audit response, and what it did NOT change (2026-09-15)

An external audit read both runtimes and ran the repo's own code against each instrument,
finding eleven places where a check passed the input it existed to catch. All eleven are
fixed. The interesting part for this file is the published number.

**`quoteAudit` 97.8% stands, re-verified under the tightened elision rule.** The fix
requires elision fragments to appear in source order within a bounded gap — before it, two
sentences from different sections joined by "..." scored 100%, in either order. Re-scoring
the 46 published quotes with the fix:

| | |
|---|---|
| pages that no longer fetch | **4** — link rot since 2026-09-08, not a scoring change |
| comparable quotes on a live page | 42 |
| re-scored with the fixed rule | **97.6%**, against the published 97.8% |
| quotes the elision fix moved | **0** |

So the fix caught nothing here, and that is the honest result rather than a
disappointment: this corpus contains no stitched quotes, so a rule that rejects them has
nothing to reject. It protects against an input these runs never carried. The 0.2-point
difference is the four rotted pages leaving the denominator, not the scorer changing its
mind about anything.

Stated plainly because the opposite reading was available and tempting: a raw recompute
across all 46 reads 89.1%, which looks like the fix exposing an inflated headline. It is
not — it is four dead links counted as failures.

## The second audit, and the pattern that survived the first fix (2026-09-15)

The response to the first audit was itself audited. Thirteen findings across the two, and
the second one's charge was that the fixes had repeated the pattern the first one named:
each was validated against the attack that motivated it and not against its mirror.

| the fix | the mirror it missed |
|---|---|
| superset stamped pre-registered | the **subset** — stripping a qualifier makes the claim STRONGER |
| challenge wordlist too narrow | it now fires on genuine **results about rate limiting** |
| junk filter guards one backend | it now starves the **counter-evidence lens** |
| probe scored vocabulary | it now misses a critic that **describes** rather than quotes |
| fixes ported, parity green | four existed only in **Python**, certified present by the test |

Two of those were regressions introduced by the first fix and were degrading live runs.

**The matcher could not be fixed where it was being fixed.** Measured: genuine rewordings
drop 8–12 content words (registered-side coverage 0.43) while a qualifier-stripping subset
drops 2 (0.71), so the bands overlap and a bidirectional rule rejected all four real
rewordings in `v10`. A hedge wordlist fails too — the second attack drops scope nouns. The
schema now asks for `hypothesisNumber`, so there is nothing to match.

**The parity test certified the drift it exists to catch.** Its markers prove a string
exists, and the row the fixes added paired a Python mechanism with a JS prompt sentence.
A marker-shape guard now rejects any row pairing a code token with a sentence — symmetric
prose is fine, a shared prompt string IS the feature — and it found a fourteenth instance
one row over on its first run.

## The third audit, 2026-09-15

The same pattern a third time, now including the fix that had just been written to name it.

| The fix | The mirror it was not tried against |
|---|---|
| number replaces text matching | the number itself is **unchecked** — gamed by typing a digit |
| short hypotheses fall back to characters | a **negation** is a tiny edit that inverts the meaning |
| markers decide on a weak harvest | a single anchor **short-circuited** them, so they never ran |
| marker-shape guard added | a marker can still match a **comment** describing the code |

**The comment was the mechanism.** `hypothesisNumber` was listed as a shared feature and
the row passed, because the string appeared in both files — in Python as the stamping
logic, and in the JS build only inside a comment reading *“the subset direction is handled
by hypothesisNumber”*. Prose about the code scored as the code, so the parity test
certified a feature the JS build did not have, in the same commit that apologised for the
sixth drift. Markers are now matched against comment-stripped source, which cost one row
its pass and made the other 52 mean something. The stripper checks itself: eating a string
would report a real shared feature as missing, and several rows legitimately prove
themselves with a shared prompt sentence.

**A non-result worth recording: porting the short fallback would have achieved parity on an
unsound mechanism.** The audit filed it as a JS bug — a character bag where Python had
`SequenceMatcher`. Both score *“output is stable”* against *“output is unstable”* as the
same hypothesis: 1.000 and 0.941. No character measure survives a negation, because a
negation is a small edit that inverts meaning. Across all 160 hypotheses in `runs/`, none
is short enough to reach that path. It was deleted from both builds rather than ported.

**And the filed reproduction did not reproduce.** The audit's examples for the character
bag — *“the effect is zero”* against *“the effect is huge”*, and against *“cats chase
mice”* — score 0.727 and 0.636, both under the 0.75 gate. The mechanism was broken; the
evidence offered for it was not. Finding the real failure took running the attack rather
than reading the report.

## Conformance, 2026-09-15

Three more drifts, found by looking for the *shape* of the last seven rather than for
another instance of any one of them. All three were invisible to every gate that was green.

| What drifted | How it stayed hidden |
|---|---|
| `quick` verified **10** claims in Python, **14** in JS | both files contain the token, so every marker row passed |
| `webText(x, 300)` **ignored the cap** in JS | the helper took one parameter; JavaScript discards extra arguments in silence |
| the depth budgets had **no shared source** | the JS suite asserted `caps.quick === 14` — a test written against the copy |

The middle one is the project's own defining bug class sitting in the helper that every
prompt goes through: seven call sites passed a length, and the JS build shipped
untruncated model text wherever the Python twin bounded it at 300 or 400 characters.

**The instrument found a real difference on its first run, and it was not a bug.**
`host_is_ambiguous("https://nature.com\@evil.xyz/x")` answers `true` in Python and
`false` in JS — and both are correct. Python's two parsers disagree on that URL; the JS
runtime's WHATWG parsing normalises the backslash, so both of its parsers agree on
`nature.com` and its WebFetch would genuinely go there. The case was kept and now pins
**both** answers with the reason, because a platform difference nobody has written down
is the same hazard as a drift — it is just one nobody will notice until the platform
moves. `out_by_runtime` is for exactly that, and it fails if either answer changes.

**Why conformance and not more markers.** A marker proves a string exists, which catches a
feature nobody ported and nothing else. It cannot see a feature ported *wrongly*, and one
marker matched a comment describing a mechanism the build did not have. Every drift on
record — nine now — was a pure function over plain data. `contract/conformance.json` asks
both runtimes the same 35 questions and compares their answers. Markers stay for prompts
and prose, which have no return value to compare.

## Every gate proves a good and a bad reference, 2026-09-15

Adopted from [ponytail](https://github.com/DietrichGebert/ponytail)'s benchmark method,
which states it better than this repo had: *"every instrument ships a `good` and a `bad`
reference and is verified by `--selftest` (the good ref must pass, the bad ref must be
caught) **before any API call**."* Its `bad` reference is defined as *"the lazy-but-plausible
version: correct on the happy path, unsafe on the adversarial input — exactly the code a
binary correctness gate passes,"* which is this project's bug class written by someone else.

The rule now runs at preflight: 47 references over 12 instruments, 9 of them gates. A
build whose gates answer wrongly exits `CONTRACT` (4) having spent no tokens. Verified by
breaking `is_prose` in the source and watching a real run refuse to start.

**The half that bites is not "has a bad reference" but "the bad reference answers
differently."** A gate can carry many cases and still never have been observed to reject
anything — which is precisely what the parity markers did for years, and what `catchRate`
did by counting a partial as a catch. Both failure shapes are now caught: a gate with no
bad reference, and a gate whose bad references answer exactly what its good ones answer.

**Writing the bad reference is where the value was.** Three things fell out of it that no
amount of reading would have produced:

- The first bad reference for `is_prose` was a navigation wordlist. It **passed** — and
  correctly. That gate detects binary wearing a text costume, not boilerplate, and it
  requires *both* signals to fail so a non-English paper is not discarded as garbage. The
  real reference is a PDF with a broken ToUnicode map, long enough to clear the 40-word
  floor so the ratio rule is what does the work. The non-English paper is now a *good*
  reference, pinning the behaviour that rule exists to protect.
- `host_is_ambiguous` had no demonstrated catch in the JS build at all. Probing for one
  found `https://[::1]/x`: the host regex stops at the first colon and reads `[`, while
  the standard parser reads `[::1]`. Both runtimes catch it, so both now have a real
  rejection on record rather than a guard nobody had seen fire.
- `webText(x, 300)` had been discarding its cap in JS for months — found while building
  the adapter, not while reading the code.

## A real run, end to end, 2026-09-15 — `v11-creatine-cognition.json`

The first thing anyone had run end to end in a while. It found two defects that 454 tests,
53 conformance references, a 53-row parity table and seven CI jobs had all been green
through — both of them in code, not in prompts, and neither reachable from any test.

**Every calibrated run had been dying at the final step.** `TypeError: object of type
'int' has no len()`. The calibration block binds `dropped` to an int counter, and that
name already held the URL-dedup LIST in the same 486-line scope, which `stats()` closes
over to publish `budgetDropped=len(dropped)`. So the run did framing, two search waves, 26
sources, 66 claims, 30 verified, the dropped-claim sample, the citation audit and the
calibration itself — 283 agent calls, ten minutes — and then threw while assembling the
report. Nothing written. Everything lost, at the moment it was all most worth having.

Nothing caught it because **no test ever ran that path**: every calibration test called
`calibration.py` directly or searched engine source for a string. `"globals()
['CALIBRATE_N'] = a.calibrate" in _main_src` is not a run.

**A mandatory field had been pointing at itself, on a quarter of all runs.**
`strongestArgumentAgainst` came back as *"See strongestArgumentAgainst field above (also
populated in dedicated field)"*, with an invented sibling key
`strongestArgumentAgainst_unused` holding `""`. Across the recorded runs that is **4 of
20**, and this one makes 5 of 21. The argument is not misfiled — searching the whole
report for it finds only the *perspective label* "Steelman-conditional-benefit". It is
missing, on the one field whose entire job is to argue against the answer.

The separation is not subtle, which is why it is now decided in code:

| | length |
|---|---|
| the four non-answers | 41, 64, 65, 74 characters |
| the sixteen genuine steelmen | 906 – 2101 characters |

A pointer **and** a short field. Either test alone is wrong: a real steelman may cite
another section mid-argument, and a short field may be a blunt honest answer.

Also fixed: the verify pool logged *"spans 9 distinct sub-question buckets (of 8)"* —
counting `(unassigned)` as a sub-question, a number larger than the total that overstates
coverage in the flattering direction.

### What the run itself did

| | |
|---|---|
| sources → claims → verified | 26 → 49 → 30 |
| confirmed / killed | 23 / 7 |
| kills by lens | support 5, counter 3, provenance 6 |
| citation accuracy | 79.3% (survivors-only 82.6%), 1 unsupported, 1 unreachable |
| calibration | n=30, κ=0.630, Scott's π=0.627, 4 flips → **calibrated** |
| per-lens κ | support 0.857, provenance 0.798, counter 0.783 |
| quotes located on page | 23/23 |
| coverage | 1 answered, 3 partial, 4 unanswered — and it says so |

**The audit demoted a claim.** Phase 7's demotion had never once fired across every run
previously reviewed; here the panel passed a claim and the blind re-fetch did not support
it. The mechanism works.

**The dropped-claim sample says the ranking does not select for verifiability.** 10 of 10
dropped claims survived (100%) against 80% of kept ones. The crashed first run measured
8/10 (80%) against 83%. Two independent measurements, same conclusion: the
`(importance, sourceQuality)` sort is not predicting which claims survive the panel. That
is a live open question, not a fixed bug.

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
