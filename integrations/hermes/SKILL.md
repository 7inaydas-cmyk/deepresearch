---
name: deepresearch
description: >
  Research that refutes itself first. Kills weak claims with a 3-lens adversarial panel, re-
  checks every citation blind against the live page, and audits its own summary for statements
  no source supports. Writes falsifiable kill criteria before it searches. Use for: 'deep
  research on X', 'is it true that X', 'settle this question', 'due diligence', 'what does the
  evidence actually say', or any question where being WRONG is expensive. Keyless search, no
  API key beyond the Claude subscription. Slower and far more rigorous than mega_research —
  use mega_research for a quick sourced answer, deepresearch when correctness matters more
  than speed.
version: 1.0.0
author: ported from the Claude Code /deepresearch harness
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [research, deep-research, multi-agent, citations, fact-check, verification, due-diligence, adversarial]
    related_skills: [mega_research, keyless-web-retrieval]
---

# deepresearch

Multi-agent research that assumes its own output is wrong until proven otherwise.

## Why this exists

Measured reality for cited AI reports:

- Citation **links** resolve over 94% of the time, but only **39-77% of citations actually
  support the claim** attached to them (arXiv:2605.06635, 14 models).
- **84.7% of final-report errors originate at the orchestrator**, not at retrieval
  (arXiv:2608.24306) - the synthesis step invents things the sources never said.
- Critical hallucinations occur **in intermediate planning steps** and are **invisible to
  end-to-end checks** (DeepHalluBench, arXiv:2601.22984).

So checking that the links work is not fact-checking. `mega_research` gets you a sourced
answer. This gets you an answer that has survived being attacked.

## How to run it

This skill runs the **shared engine** from the deepresearch repo, checked out at
`/opt/data/deepresearch-repo`. Hermes and Claude Code now run the same code, on purpose:
when they were separate copies they drifted five features apart.

**Always pass `--bg`.** The engine detaches itself and returns the paths to watch. This is
not optional: Hermes kills terminal commands at `terminal.timeout` (180s here) and a
standard run takes 6-10 minutes, so a foreground run is killed mid-flight.

**Step 1 - say roughly how long it will take, then launch:**

```bash
mkdir -p /opt/data/research/raw/dr
cd /opt/data/deepresearch-repo && DR_SEARXNG_URL=http://searxng:8080 python3 -m deepresearch \
  --question "<the fully-specified question>" \
  --depth standard \
  --out /opt/data/research/raw/dr/run.json --bg
```

`DR_SEARXNG_URL=http://searxng:8080` is what keeps this a web research tool rather than
a literature search. Without it, DuckDuckGo and Mojeek challenge this host, every
general-web backend returns zero, and the run quietly becomes scholarly-only while still
reading as complete (#8). Verified reachable from this container on 2026-09-06. If the
container is not running, `curl -s -m 5 http://searxng:8080/ >/dev/null` fails fast —
drop the variable and SAY in your report that coverage was scholarly-only.

It prints JSON immediately: `pid`, `log`, `report`, `poll`, and an `expect` duration.
Use a distinct `--out` filename per run if two could overlap.

**Optional flags, for measuring the tool rather than the topic.** Do not add these to an
ordinary research request - they roughly double the cost of the verify phase.

| Flag | Env | What it does |
|---|---|---|
| `--calibrate N` | `DR_CALIBRATE` | Re-runs the panel on N claims and reports Cohen's kappa, Scott's pi, per-lens agreement and a pre-registered gate verdict. **Needs N >= 30**; below that the gate returns `underpowered` on purpose. |
| `--sample-dropped N` | `DR_SAMPLE_DROPPED` | Verifies N claims the budget discarded and reports how often they would have survived. |
| `DR_UNTRACEABLE=strike` | | Removes untraceable sentences instead of flagging them. Default `flag`. |

**Preflight.** `python3 -m deepresearch --selftest` now exits `0` healthy, `1` failed,
`2` auth failed, `3` DEGRADED - every dependency works but no general-web backend
returns anything, so the run would be scholarly-only. On `3`, start the SearXNG
container before launching; if you cannot, run anyway and SAY in your report that
coverage was scholarly-only.

**Step 2 - poll.** Returns instantly, well inside the timeout. Relay the interesting lines
as they appear (perspectives chosen, claims killed, RESCUE firing, citation accuracy) so a
long run does not look like a hang:

```bash
tail -15 /opt/data/research/raw/dr/run.log
```

**Step 3 - when the process is gone, read the report:**

```bash
pgrep -f "deepresearch --question" || echo DONE
python3 -c "import json;d=json.load(open('/opt/data/research/raw/dr/run.json'));print(d['answerFirst'])"
```

Read the JSON for `findings`, `refuted`, `citationAudit`, `processCritique`, `coverage`,
`rescue` and `scopeContract`.

Run the selftest first if anything looks broken - it checks the credential, keyless search
(naming which backends are alive), page fetch, a model round-trip and parallel agents in
about 30 seconds:

```bash
cd /opt/data/deepresearch-repo && python3 -m deepresearch --selftest
```

To update the engine: `cd /opt/data/deepresearch-repo && git pull`.

### Timing to quote to the user

| depth | healthy search | degraded search | agents |
|---|---|---|---|
| `quick` | ~2-3 min | up to ~9 min | ~30-45 |
| `standard` | ~6-10 min | up to ~12 min | ~145-160 |
| `exhaustive` | ~15-25 min | longer | ~250 |

Wall time is dominated by search latency, not agent count: when the general web backends
are rate-limited, every query walks the whole failover chain first.

### Sharpen the question before running

A vague question wastes the whole run - the scoper will build a checklist for a question
the user did not ask. If the request is underspecified, ask 2-3 clarifying questions first,
then weave the answers into `--question`.

State any load-bearing premise explicitly. The scoper turns asserted premises into
sub-questions to *test* rather than assume - but only if it can see them.

**Better: pass what you settled as a contract, not as prose.** Write the agreed fields to a
JSON file - any subset of `decisionAtStake`, `keyQuestion`, `assumptions`,
`whatWouldChangeTheAnswer`, `hypotheses` - and add `--contract /opt/data/research/raw/dr/<slug>.contract.json`
to the command. Supplied fields are never re-derived; the model drafts only what is missing.
A malformed file exits 4 immediately, before any model call, naming the field - fix it and
relaunch. Every run also writes the contract it used beside the report as
`<out-stem>.contract.json`, so a re-run can pass it straight back.

### Choosing depth

| depth | agents | wall time | use for |
|---|---|---|---|
| `quick` | ~40 | 3-8 min | a factual check or fast second opinion. Still 3 lenses; no deepening, no citation audit, no rescue. |
| `standard` | ~140-180 | 15-30 min | **the default.** Full pipeline. |
| `exhaustive` | ~250-300 | 35-60 min | decisions with real consequences, contested topics, anything the user will act on. |

## Reading the result

Report these six things. Do not bury them.

0. **`stats.searchHealth`** - per-backend attempts and result counts. Check this FIRST.
   The general web backends (`ddg`, `ddg-lite`, `mojeek`) rate-limit and answer with a
   challenge page that parses to **zero results while reporting `status: ok`**. When they
   read 0 and only `crossref` / `wikipedia` / `hn` produced results, the run saw a
   scholarly-only slice of the web: say so, and treat coverage gaps as a search artefact
   rather than evidence that nothing exists. If the summary begins
   `SEARCH INFRASTRUCTURE FAILURE`, no backend returned anything - retry later, and never
   report it as "no sources exist".

   **KNOWN ACCOUNTING ARTEFACT (verified 2026-09-06).** `searchHealth` under-reports
   `results` for backends that DID work. The chain short-circuits (`break`) as soon as it
   has enough hits, and per-call `backend_log` entries are only recorded for backends the
   chain actually reached — so a run can show `wikipedia results=0, hn results=0` while
   Wikipedia was in fact serving every hit. Confirmed by calling `dr.web_search()`
   directly: it returned 6 Wikipedia URLs and logged `wikipedia results=6`, while the same
   backends read 0 across a full run. **Cross-check `sources` (the URLs actually fetched)
   before concluding a backend was dead.** In the 2026-09-06 test run all 10 fetched
   sources were `doi.org` — i.e. Crossref carried the run and the general web contributed
   nothing, which IS a real finding about coverage even though the per-backend counts are
   unreliable.

   **THE FIX, verified working 2026-09-06.** A local SearXNG restores general-web
   coverage on a challenged host. On the same query that returned 6 scholarly URLs
   through the degraded chain, it returned 31 results including practitioner blogs the
   scholarly tier structurally cannot reach:

       cd contrib/searxng && docker compose up -d
       export DR_SEARXNG_URL=http://searxng:8080   # from inside this container
       sh verify.sh

   `searxng` is already first in the backend chain, so nothing else changes. If
   `DR_SEARXNG_URL` is set and `searchHealth` still shows `searxng results=0`, the
   container is up but not serving JSON — run `verify.sh`, do not assume the web is
   empty.

1. **`citationAudit.citationAccuracy`** - of every verified claim, the percentage whose
   cited page, re-fetched blind, actually supports it. **The single most important number.**
   Under ~70% means treat the report as provisional and say so. Also report
   `demotedBySurvivingPanel`: claims the panel passed but whose sources turned out not to
   say what they were read as saying.
2. **`citationPartials`** - claims the blind re-fetch rated `partial`: the page points this
   way, but the statement adds scope, certainty or specificity the page does not carry.
   **A `partial` does NOT remove the claim** - only `unsupported` does - so these get
   published with nothing but a note. Measured with injected defects: of five fabrications
   the auditor caught all five, but rated three `partial`, and those three were an inflated
   number, an invented attribution, and a claim widened to every adult on earth. Check this
   list before quoting a number or an attribution.
3. **`processCritique.untraceableCount` and `untraceableStatements`** - assertions in the
   summary that trace to no verified claim. These are orchestrator hallucinations.
   **Strike them from what you tell the user**, and say you struck them. Read these, not
   `processCritique.verdict`: three fabricated sentences were appended to a real summary and
   the critic named all three while returning `material-gaps` on the clean and the degraded
   version alike. The verdict is a coarse tag, measured not to move.
4. **`coverage`** - sub-questions that came back `unanswered`. A hole in the answer, not a
   footnote.
5. **`rescue`** - present only if some sub-question lost every claim. `claimsSaved: 0`
   means the retry also failed: that part is genuinely unanswerable from the web, say so.

Also surface `refuted` (what was killed and by which lens - often more informative than
what survived), `contradictions` (never silently pick a side), and
`stats.claimsDroppedBeforeVerify` (claims never checked at all).

## Rules when presenting

- **Never upgrade the harness's confidence.** A `medium` finding stays medium.
- **A refuted claim stays refuted** even when it was the tidy answer the user wanted.
- If `confirmed` is 0 and `killed` is high, that is a real result: the sources were weak or
  the claims overstated. Say that; do not go find softer sources to fill the page.
- If the summary says `INFRASTRUCTURE FAILURE`, that is API errors, not a research finding.
- Quote the numbers with their source.

## How it works

| Phase | What happens |
|---|---|
| **Scope contract** | **(mega_research Phase 0, merged 2026-09-06)** Before decomposing: `decisionAtStake`, `keyQuestion`, `assumptions`, `whatWouldChangeTheAnswer`, and 2-4 MECE `hypotheses` each with an explicit `killCriterion`. Searches then exist to DISCRIMINATE between hypotheses, not to confirm one. Emitted as `scopeContract` in the JSON — **report the assumptions to the user; an assumption they discover at the end is a defect.** |
| Scope | Sub-question checklist + diverse perspectives. A **steelman** and a **constructor** perspective are mandatory, so the panel does not share one blind spot. |
| Search | One agent per perspective picks which results to fetch. Search itself is deterministic and free. |
| Fetch | URL-dedup (spoof-safe host parsing), extract falsifiable claims with verbatim quotes. |
| **Tiering** | **(merged)** Every source graded T1-T5 by deterministic host rules in code (`tier_of`), not model judgement. T1 primary / T2 established secondary / T3 practitioner / **T4 aggregator = discovery only, never cite as fact** / **T5 SEO-farm = excluded, exclusion reported**. Census in `stats.sourceTiers`. |
| Deepen | Gap analysis against the checklist, then follow-up waves aimed at what is missing. |
| Verify | Each claim judged by 3 **different** lenses - quote-support, counter-evidence (with real counter-searches), provenance. 2 of 3 refutations kill it. |
| Rescue | Any sub-question left with zero survivors gets a targeted primary-source re-search. |
| Audit | Every verified claim's citation re-fetched and judged **blind**. Can demote a claim the panel passed. |
| Synthesize | Merge, flag contradictions, rank by confidence. **(merged)** Also emits `answerFirst` (Pyramid Principle), `hingeNumber` (the one number the call rests on + its sensitivity), `baseRate` (outside view, or explicit flag of its absence), per-finding `sourceTier` and `factInferenceAssumption` (fact / inference / assumption), **mandatory** `strongestArgumentAgainst`, and `whatWouldChangeThisCall`. |
| Critique | Audits the plan and the summary's traceability - not just whether links resolve. |

## Merged mega_research fields - report these

Beyond the six numbered items above, surface:

- **`answerFirst`** - lead with it. Never open with process narration.
- **`scopeContract.assumptions`** - state them in the reply, not just the file.
- **`hingeNumber`** - the single number the conclusion rests on, with its sensitivity. If the
  answer flips on a 10-20% move, say so: that is a coin flip wearing a suit.
- **`baseRate`** - or its explicit absence.
- **`strongestArgumentAgainst`** - mandatory, never omit, never soften. It is often the most
  valuable paragraph in the report.
- **`whatWouldChangeThisCall`** - the named triggers for revisiting.
- **`stats.sourceTiers`** - a run that is all T3/T4 is a weak-evidence run however confident
  the prose sounds. A finding resting only on T4 must be low confidence and labelled
  aggregator-sourced.

## Cost and limits

Search is free (Hermes's own keyless `research` tool: DuckDuckGo, Mojeek, Wikipedia,
OpenAlex, Crossref, HN with failover). Model calls use the Claude Code OAuth subscription
credential at `/opt/data/.claude/.credentials.json` - **no API key and no per-token
billing**, but runs do consume subscription rate limit. If the token expires, run any
Claude Code command on the host to refresh it.

- **The panel is harsh** - it kills 55-70% of claims and occasionally kills a true one
  whose near-duplicate survives. Read `refuted` before concluding something is unsupported.
- **The scoper's checklist steers everything.** If your question hands it a premise, it may
  verify that premise rather than test it. Check `processCritique.planFlaws`.
- **It cannot make sources exist.** On a thin topic it returns a mostly-empty report and
  says so. That is the right answer, not a malfunction.
- **Search failover is driven here, not by the tool's `auto` mode.** `auto` only cascades
  `ddg` -> `ddg-lite`; when both are challenged it gives up while `mojeek`, `wikipedia`,
  `crossref`, `hn` and `openalex` are still healthy. This skill walks the full chain and
  merges results, and records what every backend said.
- **Every tier runs all 3 verification lenses.** 2 of N refutations kill a claim, so with
  only 2 lenses a 1-1 split survives and no single lens can ever kill anything - the filter
  goes inert. Cheaper tiers cut the claim COUNT, never the lens diversity.
- **The scope agent needs `max_tokens=6000`, not 3000.** The merged `scopeContract` shares
  one response with `subQuestions` and `perspectives`. At 3000 the JSON truncates and comes
  back carrying ONLY `perspectives`, and the run dies with
  `unusable plan (0 sub-questions, N perspectives)`. Fixed 2026-09-06; if that error ever
  returns, the error text now lists the keys present — missing sub-questions alongside
  present perspectives means truncation, so raise max_tokens rather than retrying blind.

## Merged-build notes (2026-09-06)

The mega_research merge added a Phase 0 framing contract, deterministic source tiering and
answer-first synthesis. Three things were fixed on top of it after end-to-end testing:

1. **Scope was split into two calls.** One call carrying strategy + a nested scopeContract +
   subQuestions + perspectives failed 3/3 live runs, dropping `perspectives` every time and
   once returning the JSON-Schema keyword `items` as data. Raising `max_tokens` fixed
   truncation but not shape. `framing` and `plan` now run separately with their own budgets.
2. **A validation adapter guards the model seam.** `subQuestions` arrived as a STRING and
   the old guard iterated it character by character into 226 one-character sub-questions.
   `as_list` / `as_str_list` reject anything that is not really a list, and the error names
   which keys actually arrived.
3. **DOIs are fetched from Crossref, not from doi.org.** The resolver is not fetchable — it
   returns ~212 bytes of JS-challenge text — and both Crossref and OpenAlex hand back
   doi.org links, so a run fetched 16 sources and extracted 0 claims. `web_fetch` now routes
   any doi.org URL to `api.crossref.org/works/<DOI>` for title, journal, year and abstract.
   Same 16 sources afterwards: **33 claims**. A resolved DOI is also re-tiered from `T?` to
   `T2` and labelled with its real journal.

`T?` in `stats.sourceTiers` means an unresolved resolver: provenance unverified. Treat an
all-`T?` run as weak evidence regardless of how confident the prose sounds.
