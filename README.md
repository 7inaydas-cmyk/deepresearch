# deepresearch

[![tests](https://github.com/7inaydas-cmyk/deepresearch/actions/workflows/tests.yml/badge.svg)](https://github.com/7inaydas-cmyk/deepresearch/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**A research CLI that writes down what would kill each of its hypotheses before it searches — then tries to refute what it finds, and reports what survived.**

Most research agents retrieve, summarise, and hand you the result. This one retrieves, then spends the rest of the run attacking what it found.

It needs a model: set `ANTHROPIC_API_KEY`, or let it use a Claude Code login already on the machine. **Search** is keyless and costs nothing — DuckDuckGo, Mojeek, Wikipedia, OpenAlex, Crossref, Europe PMC, PubMed, arXiv and Hacker News (plus a self-hosted SearXNG if you have one), no accounts, no Tavily/Serper/Exa signup. `dependencies = []`: Python 3.9+, standard library only, MIT.

Before any evidence exists, it writes a contract: the decision at stake, the assumptions it is making, and 2–4 hypotheses each with an explicit **kill criterion**. That contract ships in the output JSON, so you can check what it committed to before it went looking. It does not claim the frame is *right* — only that the frame was fixed and visible before the evidence arrived.

Then everything gets attacked. A three-lens adversarial panel tries to refute each claim; a blind auditor re-fetches every citation in a context that never saw the original quote; and a process critic reads the finished summary hunting for sentences that trace to no surviving claim.

**These numbers measure the filter, not the truth of the output.** More on that below, honestly.

> **If you want a tool that always returns an answer, this is the wrong one.**

---

## The receipt

Percentages are something you have to take on trust. This is not. From a real run, the process critic reading the tool's *own* finished summary:

```
SUMMARY SAID:   "...and said the numbers would likely increase by multiple times for GPT-4"

CRITIC OBJECTED: "Nothing in the pool supports this. Claim [2] says the opposite kind of
                  thing — that the authors had insufficient public data to estimate GPT-4's
                  footprint AT ALL. A statement of no-estimate has been upgraded into a
                  directional forecast."

UNDERLYING CLAIM: the authors had too little public data to estimate GPT-4 at all.
```

That is a **meaning reversal**, not paraphrase drift — and it was caught *after* the claim had already passed the adversarial panel, in the tool's own output, unprompted. Same run, another catch: `"'LBNL' is inserted — the claim says only 'the U.S. data center energy report'."`

And here it is policing its own conclusion. Asked whether standing desks are healthier than sitting, it identified the single number its answer rested on, then noticed the confidence interval was asymmetric **against** its own position:

```
"d = -0.15 already sits INSIDE the reported confidence interval, whereas d = -0.62 sits
 outside it. The interval is therefore asymmetric against standing: the downside case is
 supported by the paper's own numbers, the upside case is not."
```

Its answer to that question was not the satisfying one:

> *"Standing for part of the workday is not shown to be better for health than sitting — it is shown to be **achievable**."*

And this is the CLI in this repo answering the same question end to end — 25 sources,
58 claims extracted, 30 verified, 159 agent calls, 9 minutes, no search key:

```
Standing desks reliably reduce sitting time at work (~100 min/day short-term,
low-quality evidence), but there is no confirmed evidence in this review that they
improve hard health outcomes (mortality, cardiovascular disease, cardiometabolic
markers) — the sitting-time benefit itself fades by half within a year, and prolonged
static standing carries its own documented harm (varicose veins, musculoskeletal
discomfort).
```

Compare that against the Cochrane position on sit-stand desks: sitting time drops, the
evidence is low-quality, health outcomes are unproven, and the effect fades. It landed on
all four, including the fade — and it labelled its own evidence "low-quality" unprompted.

Raw logs for every run quoted here are in [`runs/`](runs/). Read the killed claims yourself.

---

## Install and run

```bash
git clone https://github.com/7inaydas-cmyk/deepresearch && cd deepresearch
python3 -m deepresearch --selftest          # ~30s, no install needed
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...          # or skip it if Claude Code is logged in here
python3 -m deepresearch --question "your question" --depth standard --out report.json --bg
```

`--bg` detaches and returns the log path immediately. A standard run takes 6–10 minutes; agent harnesses that kill commands at 180s will otherwise cut it off mid-flight.

Optional: `pip install -e ".[better-extraction]"` adds `trafilatura` for cleaner page text. Nothing else is ever required.

### Strongly recommended: your own search index

DuckDuckGo and Mojeek challenge datacentre and VPN addresses. When they do, every general-web backend returns zero, the run falls back to Crossref and Wikipedia, and you get a **scholarly-only** report that looks complete. It will tell you an intervention raised accuracy from 81% to 86%; it cannot tell you what practitioners found when they tried it. That is [#8](https://github.com/7inaydas-cmyk/deepresearch/issues/8), and self-hosting is the only real fix — every public SearXNG instance disables `format=json` precisely to stop automated use.

```bash
cd contrib/searxng && docker compose up -d
export DR_SEARXNG_URL=http://127.0.0.1:8888
sh verify.sh          # proves it serves JSON, not just that it is up
```

Two minutes, one container. On a blocked host it is the difference between six sources and thirty-one, and between a literature review and actual research.

### The selftest, on a host where backends are blocked

Not a cherry-picked green run — this is what it looks like when your IP is being challenged:

```
1. credential       ... OK (oauth, len 108)
2. keyless search   ... OK (3 hits)
      ddg-html         FAIL  results=0
      ddg-lite         FAIL  results=0
      mojeek           FAIL  results=0
      wikipedia        ok    results=3
3. page fetch       ... OK (14000 chars)
4. model round-trip ... OK ('pong')
5. concurrency      ... OK (3/3 parallel agents)

ALL CHECKS PASSED
```

Three backends down, and it still says so *out loud* rather than reporting an empty web. That distinction is the whole reason the search layer exists — see below.

---

## How a claim has to survive

| Phase | What happens |
|---|---|
| **Framing** | The contract: decision at stake, assumptions, hypotheses + kill criteria. Written before any search. |
| **Plan** | Sub-question checklist and N *perspectives* — different kinds of investigator, including a **mandatory steelman** and a **mandatory constructor**, so the panel does not share one blind spot. |
| **Search** | Keyless, multi-backend, with per-backend health reported. |
| **Fetch** | URL-dedup, then falsifiable claims, each with a verbatim quote. **PDFs are read as text** (stdlib, kerning-aware); an unreadable one is reported unreachable rather than passed on as binary. |
| **Deepen** | Gap analysis against the checklist, then follow-up waves aimed at what is missing. |
| **Verify** | Three **different** adversarial lenses — quote-support, counter-evidence, provenance. Two refutations kill a claim. |
| **Rescue** | Any sub-question left with zero survivors gets a targeted primary-source re-search. |
| **Audit** | Every verified claim's citation re-fetched **blind** and judged. Can demote a claim the panel passed. |
| **Critique** | Audits the summary for statements that trace to no verified claim. |

Three *different* lenses, not three identical skeptics: redundancy catches one failure mode repeatedly, diversity catches three. Two of three must refute — so every tier runs all three, because with only two lenses a 1–1 split survives and no single lens could ever kill anything.

## What comes out

Beyond findings and citations, the report is a decision document:

- **`answerFirst`** — the answer before any background.
- **`hingeNumber`** — the one number the conclusion rests on, and what happens to the answer if it is wrong by 2×.
- **`baseRate`** — or an explicit statement that the evidence contains none. *One case study is not a base rate.*
- **`strongestArgumentAgainst`** — required, every time.
- **`whatWouldChangeThisCall`** — concrete findings that would flip it.
- **`findings[].factOrInference`** — `fact` / `inference` / `assumption`, so inference cannot wear the costume of fact.
- **`stats.sourceTiers`** — the tier census.
- **`hypothesisVerdicts`** — every hypothesis from the framing contract, marked `killed`, `surviving` or `untested`, with back-references to the claims that decided it. The contract is adjudicated, not just written.
- **`honestLimits`** — the caveats, shipped *inside* the payload, on **every** exit including the failure ones. A limitation that lives only in a README is one the person reading a pasted JSON blob never sees.
- **`refuted[].refutedBy` and `refuted[].contradictedBy`** — every lens that killed a claim with its reasoning, and the sources the counter-evidence lens named as contradicting it. `why` used to carry the first refuter only, so a 2-1 kill discarded the second reason, and `counterSource` was demanded on every counter-lens call and read by nothing.
- **`quoteAudit`** — every verified claim's quote, and whether the engine could find it on the page it is cited to. Decided in code against the exact text the extractor was shown, not asked of a model. `stats.quoteLocation` censuses it.
- **`citationDetail[].locatedQuote`** — the blind auditor's own verbatim pull from the page, with whether that is on the page too.
- **`honestLimits.evidenceBase`** — how many citable sources this report rests on, and a `thin` flag when that is under five. The one caveat you can gate on in code without parsing English.
- **`stats.pageFetchCache`** — how many page re-reads were served from memory instead of the network. The audit re-reads a page once per claim cited to it; 18 of 30 audit fetches in each of two recorded runs were re-downloads.
- **`stats.usageUnrecorded`** — empty is healthy. A key here means the API reports a token field this build does not name, so the token totals are incomplete by exactly that much and say so. It found three on its first run, two of which nobody had predicted: the API reports cache creation as a *nested* object broken down by TTL.
- **`citationPartials`** — claims the blind re-fetch rated `partial`. These are **kept**, so read them before quoting a number or an attribution.
- **`processCritique.untraceableCount`** — read this, not `verdict`. The verdict was measured not to move when three fabricated sentences were added.

### Flags for measuring the tool itself

These exist because the tool's own claims needed testing, and they are the same
instruments the numbers below were produced with.

| Flag | Env | What it does |
|---|---|---|
| `--calibrate N` | `DR_CALIBRATE` | Re-runs the panel on N verified claims and reports Cohen's kappa, Scott's pi, per-lens agreement, the confusion matrix and a pre-registered gate verdict. Doubles the verify cost for those N claims. **The gate needs N ≥ 30.** |
| `--sample-dropped N` | `DR_SAMPLE_DROPPED` | Verifies N claims the budget discarded and reports how often they would have survived. Turns "most of the evidence is never checked" from a worry into a number. |
| — | `DR_UNTRACEABLE=strike` | Removes untraceable sentences from the summary instead of flagging them. Default is `flag`, because the critic's precision is unmeasured and deleting on an unmeasured judgement is the unearned confidence this tool exists to catch. |
| `--contract path.json` | — | A framing contract you already ratified — any subset of `decisionAtStake`, `keyQuestion`, `assumptions`, `whatWouldChangeTheAnswer`, `hypotheses`. **Supplied fields are never re-derived**; the model drafts only what is missing. A malformed file exits `4` before any model call. Every run writes the contract it used to `<out-stem>.contract.json`, so a re-run can pass it straight back and hold framing constant. |
| `--selftest` | — | Exit `0` healthy, `1` failed, `2` auth failed, **`3` degraded** — everything works but no general-web backend returns anything after 3 probes with backoff, so the run would be scholarly-only. |

**A shell pipe swallows the exit code.** `python3 -m deepresearch --selftest \| tail` reports the exit status of `tail`, not of the selftest — measured live: it printed `0` while the selftest body said `DEGRADED`. Either don't pipe it, or `set -o pipefail` first so the real code survives:

```bash
set -o pipefail
python3 -m deepresearch --selftest | tail -20; echo "exit: $?"
```

Any CI or wrapper piping `--selftest` without `pipefail` gets a false green in exactly the degraded state this check exists to catch.

```bash
python3 -m deepresearch.probes --report runs/your-run.json --out runs/probes.json
```

Injects known defects into a finished report and measures whether the citation auditor and the process critic catch them. See below for what it found.

## Source tiering is code, not vibes

Asking a model to rate a source "primary/secondary/blog" is neither reproducible nor testable — the same URL comes back graded differently on two runs. Tiering here is a pure function over host rules, shared by both runtimes from [`contract/tiers.json`](contract/tiers.json):

| | |
|---|---|
| **T1** | standards bodies, regulators, filings, preprints |
| **T2** | peer-reviewed, major press |
| **T3** | practitioner — blogs, forums, source repos |
| **T4** | aggregator — **discovery only**, never cited as fact |
| **T5** | content farm — excluded, and the exclusion reported |
| **T?** | **resolver** — `doi.org` and friends. Provenance *unverified* |

That last row matters more than it looks. A resolver is not a publisher. Grading `doi.org` as top-tier makes a predatory journal outrank an SEC filing — and during a search outage where a DOI index is the only backend still answering, the census reports *"all top-tier sources"* on the weakest evidence the run has ever had. The confidence signal inverts exactly when you need it most.

---

## Where it fails

- **The kill rate is not a quality metric.** It reports how much was removed, not whether removal was correct. There is no ground truth here and the **false-kill rate is unmeasured**.
- **The frame is unaudited.** The contract is fixed before the evidence, which is the point — but nothing checks whether the frame was the *right* one. A well-executed answer to a subtly wrong question is the failure mode this cannot catch.
- **Roughly one in eight surviving claims still fails its own citation audit.** 86.7% and 88.1% are real numbers, honestly reported, and they are not 100%.
- **It cannot make sources exist.** On a thin topic it returns a mostly-empty report and says so. That is correct behaviour, not a malfunction.
- **The panel is harsh** and occasionally kills a true claim whose near-duplicate survives. Read `refuted` before concluding something is unsupported.
- **Model cost is real.** Search is free; a standard run is a few hundred thousand tokens. It also **does not use prompt caching**, which is a decision rather than an oversight — the only prompt large enough to cache is the citation audit's, and making it cacheable requires moving the page above the statement, which was measured to move 6 of 30 audit verdicts against a judge that disagreed with itself on 0 of 30. See [ADR-0003](docs/adr/0003-no-prompt-caching.md). `stats.cacheReadTokens` reads 0 for this reason.
- **A quote can be partly real.** Across live runs on 2026-09-08 the on-page rate ran **87–97%**, lower where the sources are PDF-heavy. Most of the rest are a genuine prefix with a diverging tail, not an invention — `quoteAudit.foundFraction` says which, and the panel is told before it votes. Before this, "VERBATIM" appeared in three prompts and in no code. **The rate is a lower bound on quote fidelity, not an upper one:** the residual `partial` verdicts on PDF sources include our own extraction artifacts — our reader drops the `fi` ligature, so a page reads `signicant` and a faithful quote scores short. Hyphenation and spacing are normalised away; dropped characters inside a word are not, and cannot be without making the matcher too loose to mean anything.
- **A PDF whose font encoding defeats extraction is now refused, not passed on.** `digamoo.free.fr/neumark1994.pdf` extracted to 13% letters and zero English stopwords, and the model handed that text returned four fluent, entirely invented quotes about employment elasticities. Readable pages measure 77–96% letters and 23–39 stopwords per 1000 characters; the gate sits five times clear of the nearest good page and needs BOTH signals to fail, so a non-English paper is not thrown away as binary.
- **A thin run is published, not suppressed.** `honestLimits.evidenceBase` says how many citable sources a report rests on and flags it below five. Aborting thin runs was considered and refused: the thinnest run on record was thin because PDFs were reaching the model as raw binary, and stopping it early would have hidden the bug instead of surfacing it.
- **Cloudflare-protected publishers now fall back to the archive.** When a live read is blocked, the run retries the URL against the Internet Archive's *raw* capture — free, keyless, no account. Measured 2026-09-08: `pnas.org/doi/10.1073/pnas.2200300119` served a shell and the run settled for a 388-character Crossref abstract; the archived copy returns the full 14,000-character paper. Sources read this way carry `via: wayback` and a `snapshotDate`, because an archived page is as old as its snapshot and the provenance lens judges recency. The archive's own toolbar is never read as page text — the raw capture is requested precisely so there is no toolbar, and anything that still looks like archive furniture is refused, because that boilerplate is fluent English and would otherwise sail through the prose gate.
- **Cloudflare-protected publishers stay closed when the archive has nothing.** A stdlib fetcher cannot pass a JS challenge, so sites like PNAS answer 403. Where the URL carries a DOI the run falls back to the Crossref **abstract**, labelled `via: crossref-fallback, abstractOnly: true` so the audit knows it did not read the paper. A paid scraper with a headless browser and residential proxies genuinely wins here; nothing else in this list is closable by spending money.
- **A blocked host degrades quietly.** If DuckDuckGo and Mojeek challenge your IP the run becomes scholarly-only and still reads as complete. Check `stats.searchHealth`; fix it with [`contrib/searxng`](contrib/searxng).
- **Retrieval scale loses to paid tools, on purpose.** A DeepResearch-Bench-style comparison put effective citations at ~21 median here against Gemini 2.5 Pro DR's ~111 — Google's index versus a rate-limited keyless chain, not a tuning gap. The fix (a keyed general-web backend) is a deliberate no: `$0` marginal cost and no paid search API is the whole differentiator against every tool in that comparison, not a corner cut for now.

Each of these is tracked as an open issue with its evidence, so you can read the numbers
rather than take the bullet on trust:
[#8 scholarly-only degradation](https://github.com/7inaydas-cmyk/deepresearch/issues/8) ·
[#9 unverified claim sample](https://github.com/7inaydas-cmyk/deepresearch/issues/9) ·
[#10 critic saturation](https://github.com/7inaydas-cmyk/deepresearch/issues/10) ·
[#11 audit blindness](https://github.com/7inaydas-cmyk/deepresearch/issues/11) ·
[#12 false-kill rate unmeasured](https://github.com/7inaydas-cmyk/deepresearch/issues/12)

## The measured numbers, and what they do not prove

### The central claim, measured

The whole tool rests on one assertion: that a 2-of-3 adversarial panel is a filter rather than a coin. It was asserted for the tool's entire life and never tested. Six runs at `--calibrate 30`, against a gate whose thresholds were fixed before the instrument was built:

| Run | Kill rate | κ | n | Gate verdict |
|---|---|---|---|---|
| minimum-wage-employment | 37% | **0.86** | 30 | **calibrated** |
| mammography-forties | 17% | **0.71** | 30 | **calibrated** \* |
| standing-desks | 11% | 0.53 | 30 | usable but noisy |
| tdd-defect-rates | 30% | 1.00 | 27 | **underpowered** |
| ai-water-per-query | 52% | 0.79 | 21 | **underpowered** |
| nudge-publication-bias | 17% | 0.75 | 12 | **underpowered** |

\* *its per-lens table was lost to a bug in the synthesis-failure path, so this verdict cannot be re-checked against the per-lens precondition. Recovered from the run log; the bug is fixed.*

**Read the bottom three rows first.** All three score above the 0.6 "calibrated" threshold, and all three are rejected — the middle one on a **perfect κ = 1.00**. That run's three lenses disagreed on 74% of claims while the aggregate repeated flawlessly, and one lens was unmeasurable. A 2-of-3 vote can turn unstable raters into a stable-looking verdict, and the gate exists to notice.

So: **two runs pass, one lands in the middle band, three cannot be adjudicated.** That is the honest state. It is a necessary condition met twice, not a settled question.

> **Pre-registration and its one amendment.** Bands fixed 2026-09-06 before the instrument existed: κ ≥ 0.6 calibrated, 0.4–0.6 usable but noisy, < 0.4 noise. Amended the same day, before these runs produced any numbers, to add two preconditions: **n ≥ 30**, and **every lens individually measurable at κ ≥ 0.4**. The amendment can only make the gate stricter — it cannot promote a verdict, which is what stops it being a quiet renegotiation. Both the original and the amendment are in [`deepresearch/calibration.py`](deepresearch/calibration.py).

**Reliability is not validity.** κ = 0.86 says the panel repeats itself. It does not say the panel is right, and the two come apart badly for LLM judges — a 26-model panel has been recorded at Krippendorff α 0.77 while being systematically wrong. The false-kill rate remains unmeasured ([#12](https://github.com/7inaydas-cmyk/deepresearch/issues/12)).

### What the discarded evidence does

The budget caps verification, so most extracted claims are never checked. `--sample-dropped N` verifies some of them anyway. Five samples so far:

| Run | Dropped claims that survived | Kept claims that survived |
|---|---|---|
| minimum-wage-employment | 80% | 63% |
| mammography-forties | 90% | 87% |
| standing-desks | 80% | 90% |
| (two earlier, n=3 and n=6) | 33%, 100% | 83%, 83% |

**In four of five samples the discarded claims verified as well as or better than the kept ones.** The ranking is not selecting for verifiability. That is the unfavourable answer, it is the one the data gives, and it is tracked as [#9](https://github.com/7inaydas-cmyk/deepresearch/issues/9).

> **Correction, 2026-09-06.** This table previously read `37%, 50%, 53%, 54%, 60%, 71%` for the kill rate and `86.7%, 88.1%, 90%` for citation accuracy. **50%, 53%, 60% and 90% appear in no run, under any definition of the denominator.** The published range also dropped the four lowest kill rates — 7%, 17%, 20%, 27% — which are the unflattering ones, the runs where the panel barely killed anything. Corrected below against every recorded run, and `tools/compare_regimes.py` now regenerates this table from `runs/` so it cannot drift again. A tool that exists to catch unsupported numbers had unsupported numbers in its own README; that is the least defensible place for them.

| Measurement | Superseded regime | Current regime |
|---|---|---|
| Claims killed by the panel | 7%–71% (8 runs) | **11%–52%** (6 runs) |
| Blind citation accuracy | 82.8%–100% (8 runs) | **38.1%–90.0%** (6 runs) |
| Claims demoted *after* passing the panel | 1, across all 8 runs | **4, across 6 runs** |
| Runs where the general web returned anything | 2 of 8 | **5 of 6** |

Regenerate any time:

```bash
python3 tools/compare_regimes.py
```

**The kill-rate spread narrowed but is still wide** — 11% to 52%, against 7% to 71% before. It is the strongest argument against this tool and the low end is shown on purpose: hiding it would make the panel look far more like a calibrated filter than the data supports.

**Citation accuracy went DOWN, and that is the audit working.** The old range topped out at 100% because sources were scholarly stubs that the extractor and auditor read identically. On a real corpus the auditor stops agreeing with the extractor and the floor drops to 38.1%. A number that only looked good because nothing was being checked is worse than a bad number honestly obtained.

**The demotion path went from 1 firing in 8 runs to 4 in 6** — for the same reason. It still under-fires: three of five injected fabrications came back `partial`, and `partial` does not demote. Check `citationPartials` before quoting any number or attribution.

Earlier builds audited only the claims that *survived* the panel and unsurprisingly scored 100% — twice, both still in `runs/`. That was a rubber stamp: the weak claims were already dead before the auditor ran. The percentages above exclude those two and come from the current build, which audits the **whole** verification pool.

Six runs is a small sample and the 11–52% spread is wide. These say the filter removes a variable amount; they do **not** say what it removed was false. Nobody has run this against a set of questions with known answers and published the misses — that is the experiment that would settle it, and it has not been done.

### Retrieval, measured before and after

The same question, same regime, one thing changed — the fetcher learned to read PDFs and to refuse results that are not about the question:

| | before | after |
|---|---|---|
| Sources | 26 | 26 |
| Claims extracted | 45 | **79** |
| Unreachable citations | 2 | **0** |
| Cohen's κ | 0.8618 | **0.9268** (`calibrated`) |
| Citation accuracy | 85.7% | 76.7% |

Four primary-source PDFs were read as text for the first time, including `davidcard.berkeley.edu/papers/njmin-aer.pdf` — the paper that question exists to weigh, which had been reaching the model as `%PDF-1.5 %\x8f 135 0 obj...`.

**Citation accuracy went down, and that is the honest direction.** 79 claims drawn from full papers give far more opportunity to overstate than 45 drawn from abstracts; 76.7% with zero unreachable beats 85.7% with two unreachable and a third fewer claims.

`stats.fetchVia` now records how every source was read — `http`, `pdf`, `crossref-api`, `crossref-fallback`, `pdf-unreadable`, `failed` — so a claim cited to a paper is no longer indistinguishable from one cited to an abstract stub.

### Injected defects, which are the only ground truth here

Real output has no answer key, so both self-checks were tested by manufacturing one: take a finished report, break something on purpose, and see whether the checker notices.

```bash
python3 -m deepresearch.probes --report runs/your-run.json --out runs/probes.json
```

Five claims the citation auditor had already passed were mutated so their cited page provably no longer supports them, and the same auditor was asked again on the same page:

| Injected defect | Verdict |
|---|---|
| claim negated | **unsupported** |
| association restated as causation | **unsupported** |
| headline number × 10 | partial |
| invented "2019 Lancet consensus statement" | partial |
| scope widened to "all adults worldwide" | partial |

Nothing came back `supported`, which is the reassuring half. The other half: **only `unsupported` removes a claim.** Three of these five would have been published, flagged `partial` in a field nobody reads. So `partial` is now surfaced as its own `citationPartials` list — check it before quoting any number or attribution.

The process critic was given the same summary twice, once with three fabricated sentences appended. It **named all three** — and returned `material-gaps` both times. The verdict is saturated and cannot separate a good run from a bad one, so the report and both skills now lead with `untraceableCount` and the statement list instead.

Five probes on one report. This says the checkers catch defects of *these kinds*; it says nothing about subtler ones.

Everything above is reproducible: `runs/` holds the raw logs and probe results, and `tests/test_pipeline.py` runs the whole pipeline offline with no key and no network.

---

## How this differs from the alternatives

[GPT-Researcher](https://github.com/assafelovic/gpt-researcher), LangChain's `open_deep_research` (archived, 2026), HuggingFace smolagents' open-deep-research, ByteDance deer-flow and Stanford STORM are all retrieve-and-summarise pipelines, several of them very good at it.

None of them adversarially refute their own claims, blind-re-check their citations, or audit their own summary for hallucination. That is the whole of the difference — it is architecture, not a feature flag.

## Two things this ships that you may want regardless

**DOIs are not fetchable, and it costs you every scholarly claim.** `doi.org` redirects to a publisher that answers crawlers with a JavaScript challenge — measured, ~212 bytes of *"a required part of this site couldn't load"*. Crossref **and** OpenAlex both return `doi.org` links, so a scholarly run can fetch 16 sources and extract **zero** claims while every log line says search succeeded. The fix is to ask `api.crossref.org/works/<doi>` instead, which is keyless and carries the abstract. Same 16 sources: **0 claims → 33**.

**If your IP is challenged, run SearXNG.** DuckDuckGo and Mojeek reject datacentre and
container IPs, and no public SearXNG instance exposes `format=json` — every one tested
disables it, deliberately. Self-hosting is the only reliable fix, and it takes two commands:

```bash
docker run -d -p 8080:8080 searxng/searxng     # then set search: { formats: [html, json] }
export DR_SEARXNG_URL=http://localhost:8080
```

The chain tries it first and no-ops instantly when the variable is unset. Without it the tool
still works, but on a challenged IP it sees a scholarly-only slice of the web
([#8](https://github.com/7inaydas-cmyk/deepresearch/issues/8)).

**A rate-limited search engine looks exactly like an empty web.** DuckDuckGo answers challenged clients with an HTTP 202 page that parses to zero results *while reporting success*. A single-backend tool reads that as "no evidence exists" and the agent above it faithfully tells you so. Every backend attempt here is recorded and reported, so a null is provably a null.

## Integrations

| | |
|---|---|
| **CLI** | `python3 -m deepresearch --question "..."` |
| **Claude Code** | `./install.sh claude-code` → `/deepresearch` |
| **Hermes** | `./install.sh hermes` → `/deepresearch` |

`install.sh` symlinks rather than copies, deliberately: the two runtimes drifted five features apart when they were separate copies.

## Testing

```bash
python3 tests/test_pipeline.py     # 49 tests, offline, no key, no network
```

Every test exists because something actually broke; the comments say what. Among them: an array field that arrived as a string and became 226 one-character sub-questions, and the API's `<UNKNOWN>` serialisation artifact that appeared in roughly half of one sample of structured-output calls.

## Contributing

Two on-ramps that need no context on the rest of the codebase:
[add a keyless search backend](https://github.com/7inaydas-cmyk/deepresearch/issues/13) ·
[extend the source-tier rules](https://github.com/7inaydas-cmyk/deepresearch/issues/14).

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: every test exists because
something broke, and the comment above it says what.

## License

MIT. See [LICENSE](LICENSE).
