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

## Security note

This compose file binds to `127.0.0.1` and turns the rate limiter **off**. Both are
correct for a single local user and both are wrong on a public address. If you expose
this container, restore `limiter: true` and set a real random `secret_key`.
