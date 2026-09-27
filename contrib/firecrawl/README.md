# Self-hosted Firecrawl for deepresearch

The rendered-read layer: JS-heavy pages that the stdlib reader parses as empty
shells come back as real markdown. Opt-in by env, never a dependency:

- `DR_FIRECRAWL_URL` - the instance. NO default in the engine; unset means fully
  off. `http://127.0.0.1:3002` from the host, `http://firecrawl:3002` from inside
  the docker network. One launcher differs, by the owner's decision (2026-09-17):
  `contrib/zcode-session/drive.sh dr-launch`, with the variable unset, test-scrapes
  `https://example.com` through `127.0.0.1:3002` once and adopts the instance only
  if markdown comes back - so that launch makes one network attempt even when no
  Firecrawl runs. A set variable always wins; the engine never probes.
- `DR_FIRECRAWL_KEY` - only for a hosted instance; local mode needs nothing.

## Deployment (measured 2026-09-17)

```sh
git clone --depth 1 https://github.com/firecrawl/firecrawl.git && cd firecrawl
```

Edit the root `docker-compose.yaml`:

1. Swap the three `build:` services to their prebuilt images (the compose file
   itself documents this option): `ghcr.io/firecrawl/firecrawl`,
   `ghcr.io/firecrawl/playwright-service:latest`,
   `ghcr.io/firecrawl/nuq-postgres:latest`.
2. Pin the api's publish to loopback - local mode is unauthenticated
   (`USE_DB_AUTHENTICATION=false`, the default):
   `"127.0.0.1:${PORT:-3002}:${INTERNAL_PORT:-3002}"`.
3. To let engine runs inside sibling containers (the hermes sandboxes) reach
   it, add an external network to the API SERVICE (not playwright - beware:
   the `networks:` block nearest the top belongs to playwright-service):

```yaml
    networks:
      backend: {}
      dr-net:
        aliases: [firecrawl]
```

and at the top level:

```yaml
networks:
  backend:
    driver: bridge
  dr-net:
    external: true
    name: dr-net
```

`docker compose up -d`, then verify on CONTENT (never the status code alone):

```sh
curl -s -X POST http://127.0.0.1:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```

License: AGPL-3.0. Private loopback use carries no obligations; exposing it
publicly takes on both AGPL's network-service terms and an unauthenticated
scraping API - don't.

Failure budget: any firecrawl failure (timeout at 20s, non-200, success:false,
non-prose markdown, a malformed payload) falls back to the stdlib ladder - the
run never depends on it. The failure is disclosed as `firecrawlFailed` in the
source's meta when the direct HTTP read then serves the page. When the fallback
lands elsewhere, that source's meta names ITS own failure instead (`blockedBy`
on an abstract, `liveFetchFailed` on an archived copy, `error` on a failed read),
and firecrawlFailed is not carried - the fetch-seam tests pin exactly this.
