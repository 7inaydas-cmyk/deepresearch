# deepresearch

A research engine that refutes its own findings before showing them. Its domain is not
"search" but the gap between what a model returns and what the code is entitled to believe.

## Language

### The model seam

**Model seam**:
The one place a model's output enters the engine. Everything the engine believes about a
response is decided here, not at the call sites that consume it.
_Avoid_: API layer, LLM wrapper, boundary

**Shaped response**:
A model response coerced to the schema that requested it: every declared array is a list,
every array item is a real object carrying its required keys, every enum value is in its
enum, the boolean is a boolean. The only form a caller ever sees.
_Avoid_: validated output, parsed result, clean response

**Shortfall**:
A required field that is absent, or an array shorter than the minimum its schema declares.
Never an answer; always a defect in the response.
_Avoid_: empty result, the model declined

**Sentinel**:
The literal `<UNKNOWN>` the structured-output path intermittently returns in place of a
value. Transient and retryable, never data.

**Silent discard**:
A model-supplied value dropped by the engine with no log line. The project's defining bug
class: nine of its recorded faults had silence as their only signature.
_Avoid_: filtered out, skipped

### Verification

**Claim**:
One falsifiable statement extracted from a source, with a verbatim quote.

**Lens**:
One of three distinct adversarial readings of a claim: quote-support, counter-evidence,
provenance. Three different lenses, never three identical skeptics.
_Avoid_: judge, verifier, critic (which is a different thing)

**Panel**:
The three lenses voting on one claim. Two refutations kill.

**Refute** / **Kill**:
A lens refutes a claim; the panel kills it when two lenses refute. A killed claim is
removed from the evidence, never from the record.
_Avoid_: reject, filter, fail

**Confirmed**:
A claim that survived the panel. Means "survived a filter of unknown accuracy", not "true".

**Citation audit**:
A blind re-fetch of a confirmed claim's source, judged by an agent that has not seen the
original quote. Can demote a claim the panel passed.
_Avoid_: fact check, link check

**Partial**:
A citation-audit verdict: the page points this way but the statement adds scope, certainty
or specificity the page does not carry. A partial is kept, not demoted.

**Critic**:
The agent that audits the finished summary for statements tracing to no confirmed claim.
_Avoid_: reviewer, lens

**Untraceable statement**:
A sentence in the summary that the critic could not trace to any confirmed claim. An
orchestrator hallucination.

### Sources

**Tier** (T1–T5):
A source's grade, decided by host rules in `contract/tiers.json`, never by a model's
opinion. T4 is discovery-only; T5 is excluded.
_Avoid_: quality score, reliability rating

**Resolver**:
A host such as `doi.org` that redirects to a publisher and is not itself a source. Graded
`T?` until resolved.

**Citable**:
A tier the engine may use as sole support for a claim.

### Framing

**Framing contract**:
What is written before any search: the decision at stake, the assumptions, and the
hypotheses with their kill criteria.
_Avoid_: scope, plan (which comes after and is separate)

**Kill criterion**:
The specific evidence that, if found, would eliminate a hypothesis. Written before
searching so the search exists to discriminate, not to confirm.

**Adjudicated**:
A hypothesis is adjudicated when the evidence has marked it killed, surviving, or untested,
with back-references to the claims that decided it. An unadjudicated hypothesis is
decorative.

### Measurement

**Calibration**:
Re-running the panel on the same claims and measuring whether its verdicts repeat.
Measures reliability, never validity.

**Gate**:
The pre-registered thresholds a calibration result is read against. Amended only by dated
change, and only ever made stricter.

**Dropped-claim sample**:
Claims the verification budget discarded, verified anyway to measure whether the ranking
selects for verifiability.

**Probe**:
A defect injected into a finished report on purpose, to measure whether a checker catches
it. The only ground truth this domain has.
