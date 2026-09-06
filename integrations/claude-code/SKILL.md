---
name: deepresearch
description: >
  Deep research that refutes its own findings before showing them. Kills weak claims with a
  3-lens adversarial panel, re-checks every citation blind against the live page, and audits
  its own summary for statements no source supports. Writes falsifiable kill criteria before
  it searches. Use when being WRONG is expensive: 'deep research on X', 'is it true that X',
  'settle this', 'due diligence', 'what does the evidence actually say'. Keyless search, no
  paid search API. Slower and far more rigorous than a quick web lookup — prefer it over
  /deep-research when correctness matters more than speed.
---

# deepresearch

A research harness that assumes its own output is wrong until proven otherwise.

## Why this exists

Measured reality for cited AI reports (all verified against primary sources):

- Citation **links** resolve over 94% of the time, but only **39-77% of citations actually
  support the claim** attached to them (arXiv:2605.06635, 14 models).
- **84.7% of final-report errors originate at the orchestrator**, not at retrieval
  (arXiv:2608.24306). The synthesis step invents things the sources never said.
- Critical hallucinations occur **in intermediate planning steps** and are **invisible to
  end-to-end checks** (DeepHalluBench, arXiv:2601.22984). No evaluated system reached
  robust reliability.

So checking that the links work is not fact-checking. This harness adds two passes the
built-in `/deep-research` does not have: a **blind citation-support audit** and a
**process critic**.

## What it fuses, and from where

| Component | Origin | What it buys |
|---|---|---|
| N-vote adversarial kill (2 of 3 refutes → claim dies) | Claude Code `/deep-research` | Kills plausible-but-wrong claims |
| **3 different lenses** instead of 3 identical skeptics | Stanford STORM personas | Redundancy catches one failure mode; diversity catches three |
| Sub-question checklist + recursive gap-deepening waves | GPT-Researcher (89.11 / 94.29 citation precision/recall, DeepResearchGym) | Makes "comprehensive" measurable instead of vibes |
| Free, keyless search only | ByteDance deer-flow default | $0 search cost, no Tavily/Serper key |
| **Blind citation audit** over the full pool, with power to demote | DeepResearch Bench FACT harness | Catches the 20-60% of citations that don't support their claim |
| **Process critic** (audits the plan and traceability) | DeepHalluBench | Catches orchestrator-invented facts |
| **Rescue pass** for wiped-out sub-questions | found by this harness auditing itself | Stops an aggressive panel from silently deleting half the answer |
| **Framing contract** — decision at stake, assumptions, hypotheses + kill criteria | mega_research Phase 0 | Prevents a beautifully sourced answer to the wrong question |
| **Deterministic source tiering** (`tierOf`, T1–T5) | mega_research, hardened here | Source quality becomes a pure testable function, not model mood |
| **Answer-first synthesis** — hinge number, base rate, mandatory steelman | mega_research | Inference stops wearing the costume of fact |
| **Validation adapter at the model seam** | a live crash | A string where a list was expected is rejected, not iterated |
| URL dedup, prompt-injection hardening, host-spoof-safe labels | Claude Code built-in | Web content is treated as evidence, never as instructions |

## How to run it

**Always invoke by `scriptPath`, not by `name`:**

```
Workflow({
  scriptPath: '~/.claude/skills/deepresearch/deepresearch.js',
  args: { question: '<the fully-specified question>', depth: 'standard' }
})
```

> **Why not `name: 'deepresearch'`?** Measured, not assumed: a run launched by name
> executed a stale 655-line snapshot of this script while the file on disk was 734 lines
> with five fixes applied. Name resolution serves a registry snapshot taken when the name
> was first registered in the session, so edits made mid-session are silently ignored.
> `scriptPath` always reads the current file. If you have just edited the script, `name`
> will run the old one and you will not be told.

`args` also accepts a plain string, optionally depth-prefixed: `'exhaustive: my question'`.

### Before invoking

**Sharpen the question first.** A vague question wastes the whole run — the scoper will
invent a checklist for a question the user did not ask. If the request is underspecified
("what car should I buy", "is X worth it"), ask 2-3 clarifying questions, then weave the
answers into the question you pass.

State any load-bearing premise explicitly. The scoper is instructed to turn asserted
premises into sub-questions to *test*, not to assume — but only if it can see them.

### Choosing depth

| depth | agents | use for |
|---|---|---|
| `quick` | ~40 | a factual lookup, a sanity check, a fast second opinion. No deepening, no citation audit, no rescue. |
| `standard` | ~140-180 | **the default.** 1 deepening round, up to 30 claims × 3 lenses, citation audit, rescue pass, 2 process critics. |
| `exhaustive` | ~250-300 | decisions with real consequences, contested topics, anything the user will act on. 2 deepening rounds, up to 50 claims, 3 critics. |

Expect roughly 15 minutes at `quick`, 30-50 at `standard`, 60-90 at `exhaustive`.
Concurrency is capped at `min(16, CPUs - 2)` per workflow, so agents queue.

## Measuring the tool rather than the topic

`args: {question, depth, calibrate: N}` re-runs the panel on N claims and reports Cohen's
kappa, Scott's pi, per-lens agreement and a pre-registered gate verdict. It roughly
doubles the verify cost for those N claims, so do not add it to an ordinary research
request. **The gate needs N ≥ 30** — below that it returns `underpowered` on purpose,
because one flipped claim moves kappa by about the width of the bands at that size.

Read `calibration.gateVerdict` with `calibration.perLens` beside it. A clean aggregate
with one lens below 0.4 is capped at `usable but noisy`, because a 2-of-3 vote can turn
unstable raters into a stable-looking verdict.

## Before you trust a thin result: check search coverage

`stats.searchHealth` gives per-backend attempt and result counts. DuckDuckGo and Mojeek
answer a challenged IP with a page that parses to **zero results while reporting `ok`**,
so a run can quietly become scholarly-only and still read as complete. When every
general-web backend shows 0, say so, and treat coverage gaps as a search artefact rather
than evidence that nothing exists.

The fix is a local search index, verified working 2026-09-06 — on the same query it took
a degraded host from 6 scholarly URLs to 31 results including practitioner blogs:

```bash
cd contrib/searxng && docker compose up -d
export DR_SEARXNG_URL=http://127.0.0.1:8888
sh verify.sh
```

## Reading the result

Report these four things. Do not bury them.

1. **`citationAudit.citationAccuracy`** — of every verified claim, the percentage whose
   cited page, re-fetched blind, actually supports it. **This is the single most important
   number in the output.** Under ~70% means treat the whole report as provisional and say
   so. Also report `demotedBySurvivingPanel`: claims the panel passed but whose sources
   turned out not to say what they were read as saying. Never present a report without
   these numbers when they exist.
2. **`citationPartials`** — claims the blind re-fetch rated `partial`: the page points this
   way, but the statement adds scope, certainty or specificity the page does not carry.
   **A `partial` does NOT remove the claim** — only `unsupported` does — so these are
   published with nothing but a note. Measured with injected defects: of five fabrications
   the auditor caught all five, but rated three of them `partial`, and those three were an
   inflated number, an invented attribution, and a claim widened to every adult on earth.
   Check this list before you quote a number or an attribution from the report.
3. **`processCritique.untraceableCount` and `untraceableStatements`** — assertions in the
   summary that trace to no verified claim. These are orchestrator hallucinations.
   **Strike them from what you tell the user**, and say you struck them. Read these, not
   `processCritique.verdict`: three fabricated sentences were appended to a real summary
   and the critic named all three while returning `material-gaps` on the clean and the
   degraded version alike. The verdict is a coarse tag, measured not to move. The list
   and the count are where the information is.
4. **`coverage`** — which sub-questions came back `unanswered`. An unanswered sub-question
   is a hole in the answer, not a footnote.
5. **`rescue`** — present only when some sub-question lost every claim. `claimsSaved: 0`
   means the second attempt at primary sources also failed: that part of the question is
   genuinely unanswerable from what is on the web, and you must say so outright.

Also surface `refuted` (what got killed and by which lens — often more informative than
what survived), `contradictions` (never silently pick a side), and
`stats.claimsDroppedBeforeVerify` (claims that were never checked at all).

## Rules when presenting

- **Never upgrade the harness's confidence.** If a finding is `medium`, it stays medium.
- **A refuted claim stays refuted** even when it was the tidy answer the user wanted.
- If `confirmed` is 0 and `killed` is high, that is a real result: the sources were weak or
  the claims were overstated. Say that. Do not go find softer sources to fill the page.
- If the summary says `INFRASTRUCTURE FAILURE`, that is rate-limiting or API errors — not a
  research finding. Say so and offer to retry.
- Quote the numbers. "89.11% precision (DeepResearchGym, ICTIR 2026)" beats "very accurate".

## Reading the new fields

- **`answerFirst`** — the call, stated before any background. Lead with this.
- **`hingeNumber`** — the single number the conclusion rests on, and what happens if it is wrong by 2×. If the hinge is weak, the answer is weak, whatever the confidence labels say.
- **`baseRate`** — or an explicit statement that the evidence contains none. One case study is not a base rate.
- **`strongestArgumentAgainst`** — required. If this is thin, distrust the report.
- **`findings[].factOrInference`** — `fact` / `inference` / `assumption`. Never report an `inference` as though it were a `fact`.
- **`stats.sourceTiers`** — the tier census. **`T?` means a resolver** (doi.org): provenance unverified. An all-`T?` or all-`T3` run is weak evidence no matter how confident the prose sounds.

## DOI handling — why this matters

`doi.org` is a resolver, not a publisher, and it is **not fetchable**: it redirects to a
publisher that answers crawlers with a JS challenge (measured: ~212 bytes of "a required
part of this site couldn't load"). Both Crossref and OpenAlex return doi.org links, so a
scholarly run could fetch 16 sources and extract **zero** claims.

The extractor and the citation auditor are therefore instructed to fetch
`https://api.crossref.org/works/<DOI>` instead — keyless, and it returns title, journal,
year, authors and usually the full abstract. Measured effect on the same 16 sources:
**0 claims → 33 claims.**

## Known limits — state these, do not paper over them

- **Citation Accuracy is scored over the whole verification pool**, not over survivors.
  Auditing only survivors made it a rubber stamp — it returned 100% on three consecutive
  live runs because the weak claims were already dead. It is now an independent number and
  will vary. A claim can pass the adversarial panel and still be demoted by the audit: the
  panel judges whether the *argument* holds, the audit judges whether the cited *page*
  actually says it. Demoted claims appear in `refuted` marked `citation-audit`.
- **The panel is deliberately harsh** — verifiers default to refuting when uncertain. On a
  hard topic it will kill 60-75% of claims, and it sometimes kills a true claim whose
  near-duplicate survives. Read `refuted` before concluding something is unsupported.
- **The scoper's checklist steers everything downstream.** If your question hands it a
  premise, it may verify that premise rather than test it. State premises as things to
  test, and read `processCritique.planFlaws` — that is where this shows up.
- **It cannot make sources exist.** On a topic with no primary sources, it correctly returns
  a mostly-empty report. That is the right answer, not a malfunction.

## Cost

Search is free — the harness uses built-in `WebSearch` and `WebFetch` only, with no paid
retrieval key anywhere. The only cost is Claude tokens. A `standard` run is on the order of
5M subagent tokens; `exhaustive` roughly double.
