# deepresearch

[![tests](https://github.com/7inaydas-cmyk/deepresearch/actions/workflows/tests.yml/badge.svg)](https://github.com/7inaydas-cmyk/deepresearch/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**A research CLI that writes down what would kill each of its hypotheses before it searches — then tries to refute what it finds, and reports what survived.**

Most research agents retrieve, summarise, and hand you the result. This one retrieves, then spends the rest of the run attacking what it found.

It needs a model: set `ANTHROPIC_API_KEY`, or let it use a Claude Code login already on the machine. **Search** is keyless and costs nothing — DuckDuckGo, Mojeek, Wikipedia, OpenAlex, Crossref and Hacker News, no accounts, no Tavily/Serper/Exa signup. `dependencies = []`: Python 3.9+, standard library only, MIT.

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
| **Fetch** | URL-dedup, then falsifiable claims, each with a verbatim quote. |
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
- **Model cost is real.** Search is free; a standard run is a few hundred thousand tokens.

## The measured numbers, and what they do not prove

| Measurement | Value | Denominator |
|---|---|---|
| Claims killed by the panel | 37%, 50%, 53%, 54%, 60%, 71% | 6 runs, 10–42 claims each, Sept 2026 |
| Blind citation accuracy | 86.7%, 88.1%, 90% | full verification pool: 30, 42, 36 claims |
| Claims demoted *after* passing the panel | measured, non-zero | same runs |

Earlier builds audited only the claims that *survived* the panel and unsurprisingly scored 100%. That was a rubber stamp — the weak claims were already dead before the auditor ran. The numbers above are from the current build, which audits the **whole** verification pool. Do not quote the old 100%s at me; they are in the git history and they were meaningless.

Six runs is a small sample and the 37–71% spread is wide. These say the filter removes a lot; they do **not** say what it removed was false. Nobody has run this against a set of questions with known answers and published the misses — that is the experiment that would settle it, and it has not been done.

Everything above is reproducible: `runs/` holds the raw logs, and `tests/test_pipeline.py` runs the whole pipeline offline with no key and no network.

---

## How this differs from the alternatives

[GPT-Researcher](https://github.com/assafelovic/gpt-researcher), LangChain's `open_deep_research` (archived, 2026), HuggingFace smolagents' open-deep-research, ByteDance deer-flow and Stanford STORM are all retrieve-and-summarise pipelines, several of them very good at it.

None of them adversarially refute their own claims, blind-re-check their citations, or audit their own summary for hallucination. That is the whole of the difference — it is architecture, not a feature flag.

## Two things this ships that you may want regardless

**DOIs are not fetchable, and it costs you every scholarly claim.** `doi.org` redirects to a publisher that answers crawlers with a JavaScript challenge — measured, ~212 bytes of *"a required part of this site couldn't load"*. Crossref **and** OpenAlex both return `doi.org` links, so a scholarly run can fetch 16 sources and extract **zero** claims while every log line says search succeeded. The fix is to ask `api.crossref.org/works/<doi>` instead, which is keyless and carries the abstract. Same 16 sources: **0 claims → 33**.

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

## License

MIT. See [LICENSE](LICENSE).
