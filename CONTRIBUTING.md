# Contributing

## The one rule

Every test in `tests/test_pipeline.py` exists because something actually broke, and the
comment above it says what. If you fix a bug, add the test that would have caught it, and
write down what the failure looked like. A test with no story attached is a test nobody
will dare delete in two years.

## Running the tests

```bash
python3 tests/test_pipeline.py        # the engine: no API key, no network, a few seconds
python3 tests/test_conformance.py     # the python build answers contract/conformance.json
node tests/claude-code/conformance.mjs   # the JS build answers the SAME file
cd tests/claude-code && node test-workflow.mjs   # the JS build end to end, model stubbed
python3 tests/test_parity.py          # neither build is missing a feature the other has
```

The suite stubs the model and the network, so you can change the pipeline and see the
consequences without spending a token. If your change needs a live call to be tested, it is
probably in the wrong place — push the judgement into a pure function and test that.

## Changing pure decision logic

A matcher, a schema leaf, a tier lookup, a normaliser — anything that is a function from
plain data to plain data — is where every drift in this repo has happened, nine of them,
each one silent. Add the case to `contract/conformance.json` in the same change. Both
runtimes answer that file, so a fix that lands in one build and not the other fails CI
instead of shipping under a green parity line.

`tests/test_parity.py` is the other half and does a different job: it proves a marker
string exists in each build. That catches a feature nobody ported; it cannot catch one
ported wrongly, and it once passed a row whose JS marker was a *comment describing the
mechanism*. Markers for prompts and prose, conformance for answers.

If the two builds must genuinely differ because the platform differs — URL parsing is the
real instance — use `out_by_runtime` and say in `why` what makes the difference correct.
It pins both answers, so either one moving still fails. It is not a way to excuse drift.

## Adding a search backend

`deepresearch/search.py`, standard library only. Add an implementation, register it in
`_IMPL`, and put it in `DEFAULT_CHAIN` where it belongs — general web first, then
independent indexes, then scholarly and practitioner sources.

Two requirements:

1. **Raise on a challenge page.** Several engines answer a rate-limited client with HTTP
   200 or 202 and a body that parses to zero results. Returning `[]` for that is a lie: it
   is indistinguishable from "the web contains nothing on this topic". Detect it and raise,
   so `_note` records a failure and `health()` reports it.
2. **Prefer fetchable URLs.** A link that redirects into a JavaScript challenge is worth
   nothing downstream. OpenAlex's `landing_page_url` is usually just the DOI again; its
   `pdf_url` is often a real publisher page. Reach for the one that can actually be read.

## Adding or changing a source tier, or a depth budget

Edit `contract/tiers.json` or `contract/depths.json` — **not** the Python and not the
JavaScript. Then run `python3 tools/sync_tiers.py` and commit what it regenerates. Both runtimes read
those files precisely so a domain cannot be graded T1 in one runtime and T3 in the other,
and so `quick` cannot mean 10 claims in one and 14 in the other. Both have happened. CI
checks that every rule compiles, every tier is rankable, and the generated JS blocks match
their source byte-for-byte.

Before promoting a host to T1, ask whether it is a *publisher* or a *resolver*. `doi.org`
resolves to anything, including a predatory journal; grading the resolver top-tier makes
that journal outrank an SEC filing. Resolvers belong in `resolvers`, and get `T?` until
something actually reads the record behind them.

## Changing a prompt

Prompts live inline, deliberately: they are the product, and a template indirection layer
makes them harder to read and review than the thing it saves. Keep them readable, and keep
the reason for a constraint next to the constraint.

If you widen a schema, split the call rather than adding a field. One call carrying four
responsibilities behind three levels of nesting failed 3 out of 3 live runs here, dropping
the same field every time. Raising `max_tokens` fixed truncation and did nothing for shape.

## Things that will be rejected

- A benchmark number with no denominator, no date, and no committed log.
- Softening an honest failure message. If a run was rate-limited, the report says it was
  rate-limited — never "no sources were found".
- Removing a lens to make a tier cheaper. Two of N must refute, so with two lenses a 1–1
  split survives and the panel can never kill anything. Cut the claim count instead.
