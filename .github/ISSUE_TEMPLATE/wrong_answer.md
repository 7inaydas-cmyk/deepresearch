---
name: Wrong or badly-reasoned answer
about: The pipeline ran fine but the research was poor
labels: research-quality
---

These are the most useful reports, and the hardest to act on without evidence.

**The question you asked** (verbatim).

**What it answered, and what the right answer is** — with a source, if you have one.

**Attach the full `--out` JSON.** The interesting fields:

- `scopeContract` — did it frame the question wrongly *before* searching? Nothing in the
  pipeline audits the frame, so this is a known blind spot.
- `refuted` — was a true claim killed? The false-kill rate is unmeasured, and a report of
  one is genuinely valuable.
- `citationAudit` — roughly one in eight surviving claims still fails its own audit.
- `processCritique.untraceableStatements` — did the summary assert something the claims
  did not support, and did the critic miss it?
- `stats.sourceTiers` — an all-`T3` or all-`T?` run is weak evidence however confident the
  prose sounds.
