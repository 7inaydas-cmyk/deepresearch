# A local search index for deepresearch

Fixes [#8](https://github.com/7inaydas-cmyk/deepresearch/issues/8): on a host whose IP
DuckDuckGo and Mojeek are challenging, every general-web backend returns zero results
**while reporting `status: ok`**. The run falls back to Crossref and Wikipedia and
produces a scholarly-only report that reads as complete. It will happily tell you a
technique raised accuracy from 81% to 86%; it cannot tell you what it costs, what broke
when practitioners tried it, or who publicly disagrees.

Public SearXNG instances are not a workaround. Every one tested disables `format=json`
specifically to prevent automated use, so pointing `DR_SEARXNG_URL` at someone else's
instance does not work — and would not be polite if it did.

## Setup

```bash
docker compose up -d
export DR_SEARXNG_URL=http://127.0.0.1:8888
sh verify.sh
```

`verify.sh` is the step people skip and should not. A SearXNG that answers on `/` but
403s on `format=json` fails in exactly the shape this issue is about: the pipeline sees
an empty result list and reports that the web has nothing to say.

`searxng` is already first in the engine's backend chain, so nothing else changes.

## Measured, on a challenged host

Same query, before and after:

| | Results | What came back |
|---|---|---|
| degraded chain | 6 | Crossref and PubMed only |
| local SearXNG | 31 | plus `datacolada.org`, `bayesianspectacles.org`, `behavioralscientist.org`, `bbc.com` |

The added sources are practitioner analysis and public dissent — the material the
scholarly tier structurally cannot reach, and the material the tool's own "practitioner"
and "affected end user" perspectives were being asked to search for and could not find.

## From another container

If deepresearch runs inside a container (the Hermes build does), `127.0.0.1` on the host
is not reachable from it. Put both on one user-defined network and address SearXNG by
name:

```bash
docker network create dr-net
docker network connect dr-net searxng
docker network connect dr-net <your-agent-container>
# then, inside that container:
export DR_SEARXNG_URL=http://searxng:8080
```

`docker network connect` attaches a running container without restarting it.

## It will rate-limit itself, and that used to be silent

One research run makes roughly 90 searches in a few minutes. Measured 2026-09-06: a
single run suspended **every** engine in SearXNG's default set — brave and google cse
"too many requests", duckduckgo "timeout", startpage "CAPTCHA". The instance then
answers `200 OK` with an empty result list, and the next run reads that as *the web has
nothing to say*, which is the exact failure self-hosting was supposed to end.

Two changes, both shipped here:

- **`settings.yml` enables a much wider engine pool** (bing, qwant, wikipedia, wikidata,
  semantic scholar, crossref, pubmed, arxiv, github, stackoverflow, hackernews, reddit
  alongside the defaults). They do not share a rate limit, so load spreads instead of
  concentrating. Verified: with five providers still suspended, queries returned 20+
  results carried by the rest.
- **The engine now raises instead of returning an empty list** when SearXNG reports
  every upstream engine unresponsive. The message names them and says the instance is
  rate-limited rather than broken, so the run falls through to the next backend and the
  reason ends up in `searchHealth` rather than nowhere.

If you see this, wait a few minutes or enable more engines. Nothing is wrong with the
container.

## Check what your engines actually return

`qwant` is **disabled** in the shipped settings, and the reason is worth stating.

Enabled on this instance, every single Qwant result was **fabricated**: a nonsense
domain with a gibberish title, interleaved one-for-one with Bing's genuine results, so
half of every result page was invented.

```
bing     https://pmc.ncbi.nlm.nih.gov/articles/PMC9351501/   "No evidence for nudging after adjusting…"
qwant    http://dawedep.hu/cunfone                           "Uno nudge publication bias effect"
bing     https://www.pnas.org/doi/10.1073/pnas.2200300119    "How effective is nudging? A quantitative…"
qwant    http://ug.pn/jikuvioha                              "Bo cedlamceh nudge publication bias"
```

The pipeline did not cite any of it — the source picker rejected them — but it cost real
coverage: **11 of 15 pick calls in one run returned nothing**, and that run finished with
12 verified claims instead of 30. It reads in the logs exactly like the model being
fussy, which is why it took reading the raw SearXNG response to find.

A search engine injecting invented sources into a tool built for factual correctness is
the worst failure available here, and unknown hosts default to the *citable* T3 tier — so
had the picker been more permissive, fabricated domains would have entered the evidence
pool.

**If you enable engines beyond the shipped set, look at their raw output first:**

```bash
curl -s "http://127.0.0.1:8888/search?format=json&q=any+question"   | python3 -c "import json,sys; [print(','.join(r.get('engines') or []), r['url'][:70]) for r in json.load(sys.stdin)['results'][:20]]"
```

## Security note

This compose file binds to `127.0.0.1` and turns the rate limiter **off**. Both are
correct for a single local user and both are wrong on a public address. If you expose
this container, restore `limiter: true` and set a real random `secret_key`.
