---
status: accepted
date: 2026-09-22
---

# The scraping-library seam: a scraper is reached behind the fetch seam, never imported

Every page enters through the fetch seam — `web_fetch` (`deepresearch/engine.py:267`) —
where read provenance is recorded. The seam is deep, so a scraping library's leverage sits
exactly there: rendering, anti-bot work, extraction. Decided: a scraper is reached from
outside, as an opt-in sidecar the run survives losing — firecrawl's exact posture ("Opt-in
by env, never a dependency", `contrib/firecrawl/README.md:4`; failures fall back to the
stdlib ladder, `:62`) — never an in-process import: `dependencies = []` holds
(`pyproject.toml:18`), and the deletion test stays trivial: delete the adapter and nothing
else moves.

## The first concrete case: ScrapeGraphAI

Evaluated 2026-09-22 — MIT, 31.2k stars, actively maintained; PyPI: `Python <4.0, >=3.12`,
"based on LangChain which uses LLM and direct graph logic". Rejected on four grounds, each
load-bearing alone:

**The stdlib constraint.** This repo is `dependencies = []` on Python 3.9+
(`pyproject.toml:18`, `:6`; `README.md:12`). The evaluation recorded ~25 runtime
dependencies — five langchain packages, playwright, undetected-playwright, tiktoken,
pydantic, ddgs — against a stated floor of Python >=3.12 (verified on PyPI that day), a
major version above this repo's.

**The no-key doctrine.** Every ScrapeGraphAI page costs an LLM call. The deployments hold
no keys (ADR-0005): model calls ride harness logins or one declared key-env at the model
seam. The sidecar variant needs a key-env that does not exist here, or a local Ollama
model nobody has measured — an asserted-never-measured model inside the evidence path, the
refusal ADR-0004 already made once.

**Seam overlap.** Its fetch half — headless rendering for JS-heavy pages — is already
owned by the firecrawl sidecar, which holds exactly this posture. A second implementation
behind the same seam doubles the ops surface without adding a capability the interface
lacks.

**Contract collision.** Its extraction is LLM-guided: the output is a model's summary of a
page, not the page — sitting upstream of the verbatim-quote contract the citation audit
polices. Quote location is decided against the exact text the extractor was shown
(`README.md:166`), so a summary there makes the instrument certify quotes no page
contained, and the audit's blind re-fetch polices quotes that never existed — prose the
prose gate would wave through.

## Considered options

**An optional extra, the `better-extraction` precedent** (`pyproject.toml:21`). Rejected:
trafilatura only cleans text a fetch already obtained — a transform whose output stays
page text. ScrapeGraphAI replaces the page with a summary, so the extra imports the
contract collision and the Python floor too.

**A scraper sidecar now, beside firecrawl.** Rejected: the no-key doctrine leaves nothing
to power its extraction, and the rendering capability it adds is already owned.

## What would reopen this

Adopt a scraper sidecar only when both halves hold: **firecrawl's rendering measurably
fails on real anti-bot blocks** — the gap `README.md:281` names — blocked reads the
wayback fallback cannot cover, counted in the fetch stats; **and the local model's
extraction passes the same conformance References every other adapter answers to**
(`contract/conformance.json`): output arriving as text a quote can be located in,
surviving the prose gate, carrying read provenance the citation audit can read.

## Consequences

`dependencies = []` and `requires-python = ">=3.9"` are unchanged. Above the fetch seam
the evidence path stays single-model: every page the engine reasons about was obtained by
code this repo can read. Future import proposals should start from this file.
