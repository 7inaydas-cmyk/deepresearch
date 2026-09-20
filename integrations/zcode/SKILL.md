---
name: deepresearch
description: >
  Deep research that refutes its own findings before showing them, run BY this agent on
  the session's own subscription - no API key, no external process. A 3-lens adversarial
  panel kills weak claims, every citation is re-checked blind against the live page, and
  the summary is audited for statements no source supports. Kill criteria are written
  before searching. Use when being WRONG is expensive: 'deep research on X', 'is it true
  that X', 'settle this', 'due diligence', 'what does the evidence actually say'. Slower
  and far more rigorous than a quick web lookup. Default depth is standard (~150 model
  judgements); prefix 'quick:' or 'exhaustive:' to change.
---

# deepresearch — run on THIS agent

You are both the orchestrator and the runtime. The pipeline below is the repo's. Seven
prompt builders, every schema, and every deterministic checker are **imported from the
repo, never paraphrased**, so those phases cannot drift from the engine the way
hand-copied skills do. The one exception is the synthesis instruction list, which has
no importable builder — phase 8 says so and names where it lives.

## 0. Resolve the checkout and the depth

This skill file is symlinked from the deepresearch repo. Resolve it:

```bash
readlink -f ~/.zcode/skills/deepresearch/SKILL.md   # -> <repo>/integrations/zcode/SKILL.md
```

All `python3` calls below run with cwd `<repo>`. Depth comes from the question prefix
(`quick:` / `standard:` / `exhaustive:`, default **standard**); budgets from
`contract/depths.json` (standard: 6 perspectives, 16 wave-1 sources, 1 deepening round,
30 claims verified, citation audit ON, 2 critics, rescue ON).

Render prompts with the repo's builders — never write your own variant:

```bash
python3 -c "from deepresearch.engine import p_framing; print(p_framing(question))"
```

Validate every structured reply with the repo's seam, and treat problems the way the
engine does (ADR-0001): re-ask once naming the violation, then drop the item — never
coerce a leaf:

```bash
python3 -c "import json,sys; from deepresearch.engine import shape, S_VERDICT; \
  print(json.dumps(shape(S_VERDICT, json.load(sys.stdin))[1]))"
```

That snippet validates ONE object. When a subagent returns an ARRAY of per-item
objects (the lens verdicts in phase 5), validating the array against the per-item
schema reports `response was list, not an object` — every valid reply flagged, the
opposite of what the seam is for. Wrap it:

```bash
python3 -c "import json,sys; from deepresearch.engine import shape, S_VERDICT; \
  wrap={'type':'object','required':['verdicts'],'properties':{'verdicts': \
  {'type':'array','items':S_VERDICT}}}; \
  print(json.dumps(shape(wrap, json.load(sys.stdin))[1]))"
```

Subagents return JSON and nothing else — say so in every dispatch.

## Mode A - stdio: the ENGINE drives, this window is the model (preferred)

Since ADR-0005 the engine can run its whole pipeline with the driving window as its
model transport - every retry, sentinel recovery, schema shaping, ranking and the
2-of-3 kill rule executed by the engine's audited code, not re-orchestrated by hand.

```bash
bash <repo>/contrib/zcode-session/drive.sh dr-launch "<question>" standard
```

Search backend: the driver adopts a local SearXNG automatically when one answers
(`127.0.0.1:8888`, then `:8080`) and says so; an explicit `DR_SEARXNG_URL` always
wins. Do NOT conclude "the keyless web is dead from this machine" without checking
that: with the var unset the searxng backend silently self-skips, and once DDG and
Mojeek are blocked the chain falls through to Wikipedia/Crossref filler - which
looks exactly like "the web has nothing" (measured 2026-09-16, a session restarted
in Mode B on that false verdict while the instance was alive the whole time).

Page rendering (optional): `DR_FIRECRAWL_URL` points the fetch layer at a
self-hosted Firecrawl. There is NO default - unset means fully off and zero
network attempts. Set it to `http://127.0.0.1:3002` on the host or
`http://firecrawl:3002` from inside the docker network (see
contrib/firecrawl/README.md for the deployment recipe).
Pages are scraped to rendered markdown BEFORE the stdlib reader runs - the point
is JS-heavy pages the stdlib reads as empty shells - and any Firecrawl failure
falls back to the normal ladder, so it can never take a run down. `via:
"firecrawl"` on a source says the rendered read served it.

Then loop: `dr-next` prints the pending request; read its `prompt` (and `schema`),
compose the reply as that subagent would, and answer with ONE JSON object:

```bash
bash <repo>/contrib/zcode-session/drive.sh dr-answer '{"reply": "ok"}'   # probe shape
```

Rules of the loop:
- Answer EVERY request - the engine blocks until a matching-id reply arrives, and a
  window that stops answering is the protocol's one failure mode (a rater that never
  answers; preflight refuses cleanly if the first probe goes unanswered).
- One request at a time, by id. The driver compacts your JSON to one line; the
  exchange is one readline per request.
- Answer as the subagent, not as yourself: the prompt carries the identity block,
  the schema, and the task. Real content, real hedges, no meta-commentary.
- Phases are the engine's: you will see framing, plan, extraction (page text is IN
  the prompt - the engine fetched it), gap analysis, lens verdicts, the blind audit,
  restate-or-drop, synthesis, and the critic. The report lands at
  `$DR_RUN_DIR/report.json` with the same fields the CLI produces,
  `stats.transport: "stdio"`.

**What Mode A does NOT give you (say this to the reader, don't bury it):** one
window - you - plays every role: extractor, all three verification lenses, the
citation auditor, synthesis and the critic, in ONE conversation. Lens independence
and audit blindness are NOT guaranteed here; a later role remembers what an earlier
role composed. What does still run in code is the schema shaping, the kill tally,
the citation arithmetic and the ranking. The report carries `singleRater: true` and
an `honestLimits.singleRater` note saying exactly this - do not strip them. Choose
Mode A for the engine's code-level guarantees at minimal moving parts; choose Mode B
when rater independence matters, because its subagents genuinely do not share a
context. Mode B is also where Mode A's prompts come from.

## Mode B - the phases (hand-orchestrated)



**1. Framing** (one subagent, `p_framing` + `S_FRAMING`): the contract — decision at
stake, key question, assumptions, what would change the answer, 2-4 hypotheses each
with a killCriterion. Written BEFORE any search. Log the hypotheses.

**2. Plan** (one subagent, `p_plan` + `S_PLAN`): 4-8 sub-questions and the perspectives
(mandatory steelman, mandatory constructor — the repo's prompt says exactly how).
Cap perspectives at the depth budget.

**3. Search + extract** (one subagent per perspective, in parallel — up to 6, then the
deepening wave): each searches its lens with WebSearch (2-3 queries, refined), picks
3-5 primary sources, WebFetches each, and extracts 2-5 falsifiable claims per source
with VERBATIM quotes — the extraction prompt is the repo's `p_extract`. The subagent
must run the deterministic checks itself before returning, per claim:

```bash
python3 -c "import json,sys; from deepresearch.engine import quote_span, tier_of; \
  q=json.load(sys.stdin); print(json.dumps({'quoteCheck': quote_span(q['page'], q['quote']), \
  'tier': tier_of(q['url'], q['title'])[0]}))"
```

(pass the page text it fetched and each quote; the page never needs to come back to
you). Return records carrying the fields the later phases actually read — a claim
without these is dropped by `p_verify` or scores zero:

- source: `url`, `title`, `tier`, `via`, `claims` (count), `sourceQuality`, `publishDate`
- claim: `claim`, `quote`, `quoteCheck`, `importance`, `subQuestionIndex`, `sourceUrl`

Dedup across perspectives by URL **and by identity**: the same paper is routinely
reachable under two URLs (PMC and the publisher — the live run double-counted the
Sandkühler trial as two sources because URL dedup alone cannot see they are one).
Normalize on DOI where present, else title, and merge.

**4. Deepen** (one subagent, `p_gap` + `S_GAP`): coverage vs the checklist,
contradictions, follow-up searches; run the follow-up wave as another set of extractor
subagents.

**5. Rank + verify** — ranking is code, not judgement: run `citable_only` FIRST (T5
content farms are excluded from the verify pool entirely — the engine never ranks
what it refuses to cite), then `coverage_balanced` on the citable claims with the
depth's `max_verify`. Then **three lens subagents in parallel** (support, counter,
provenance), each given ALL claims with prompts rendered by `p_verify` (the counter
lens runs its own contradiction-hunting WebSearch), each returning `{"verdicts": [...]}`
— one `S_VERDICT` per claim, validated with the array wrapper above. The lenses never
see each other. Apply the kill rule IN CODE - it is importable, so do not hand-count:
`python3 -c "from deepresearch.engine import tally_verdicts; ..."` over each claim's
verdict list gives `(refuted, errored, survives, is_refuted)` with the engine's own
2-of-3 arithmetic; too-few-verdicts is UNVERIFIED, never killed; a claim the counter
lens refutes must name `counterSource`. A lens verdict that never arrived is not a
pass — default to refuted when genuinely uncertain, per the repo's instruction. (A
window used to hand-count while believing it had followed code - both rules now have
importable functions with conformance references.)

**6. Rescue** — any sub-question with zero survivors gets one targeted primary-source
re-search (extractor subagent), re-verified by the same three lenses.

**7. Blind citation audit** (two subagents in parallel, ~half the pool each): for each
claim send ONLY the claim text and URL (never the quote) with the repo's `p_fact`
prompt; the auditor fetches the page itself and rules supported/partial/unsupported/
unreachable. Two disciplines the engine treats as load-bearing:
- **The pool is every claim that entered the panel** (`voted`, killed claims
  included, rescue claims included) - not survivors only. Auditing only what the
  lenses already cleared measured 100% on three consecutive live runs: a rubber
  stamp, not an audit.
- **An auditor call that returned nothing is not a citation that failed** - count it
  as `auditErrors`, exclude it from the accuracy denominator, and REPORT it.
  Dropping it silently makes citationAccuracy improve under degradation.

`unsupported` demotes. A `partial` on a SURVIVING claim is not kept as-is and not
silently dropped: **restate-or-drop** - one subagent rewrites the claim to what the
auditor's `locatedQuote` actually supports (the repo's `p_restate` prompt), the
restated claim is re-audited with `p_fact`, and the re-audit verdict decides:
supported → the weakened claim replaces the original (`restatedFrom` preserves it);
partial or unsupported again → demote, exactly like `unsupported`. Apply the
demotion set in code: `python3 -c "from deepresearch.engine import demotion_set"`
carries the engine's rule (plain `partial` with no re-audit verdict does NOT demote -
no deterministic verdict, no kill). `unreachable` ≠ `unsupported` — an unread page is
an infrastructure limit, not a finding.

**8. Synthesis** (one subagent): confirmed claims only, the repo's synthesis rules —
answerFirst, hingeNumber, baseRate, strongestArgumentAgainst (mandatory, real — never
a pointer), `factInferenceAssumption` labels (that is the field's real name:
fact/inference/assumption), hypothesisVerdicts with `hypothesisNumber` for EVERY
hypothesis (its H-number, or 0 for anything invented after the evidence). There is
no importable builder for this one prompt — the instruction list lives inline in
`_synthesize` (engine.py); transcribe it from there and re-check it against the
engine when the repo changes. The seven builders that DO import are imported; this
is the one place the no-paraphrase rule bends, and it says so.

**9. Stamp + critique** — deterministic, in code: stamp `preRegistered` via the repo
(`_hyp_mismatch` + hypothesisNumber rules); compute `citationAccuracy` over the FULL
verified pool; `_evidence_base` for the thin flag. **Persist every artifact to disk
BEFORE dispatching the critics** — framing, ranked pool, lens verdicts, audit rows,
and the synthesis summary and findings as their own files. The live run skipped this
and the critics had to audit the verdict reasonings instead of the summary, because
that was the only artifact that existed; a critic cannot audit text it cannot read.
Then two critic subagents with `p_critic`: sentence-by-sentence traceability of the
summary AND findings against the claim pool (`untraceableVerbatim` copied exactly),
coverage gaps, plan flaws. Report `untraceableCount` and the statements — not the
critic's verdict tag.

## Report and present

Write the full JSON report (same field names as the CLI) to
`~/deepresearch-reports/<slug>-<timestamp>.json` beside a `.md` run log, then present:
**answerFirst first**, then the four numbers that must never be buried —
`citationAccuracy` (with the survivors-only number beside it), `untraceableCount`,
coverage (unanswered sub-questions), rescue result — then refuted claims and what
killed them, `hypothesisVerdicts` with their stamps, and `honestLimits`. Never upgrade
a finding's confidence. A refuted claim stays refuted. If search was challenged or
scholarly-only, say so as an artefact, not as evidence of absence.

## Honesty rules that travel with the pipeline

Default to refuting when uncertain · `partial` does not demote but is always surfaced ·
an unread page is `unreachable`, never `unsupported` · quotes are checked against the
page in code (`quote_span`), and a quote only partly on the page is reported as such ·
kill criteria are written before searching and adjudicated after · nothing is struck
from the summary silently · every report carries `honestLimits` even when thin or
degraded.
