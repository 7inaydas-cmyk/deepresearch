---
status: accepted
date: 2026-09-07
---

# A supplied framing field is never re-derived, and a malformed one is a hard error

The engine accepts a framing contract from outside (`--contract`, `args.contract`) holding
any subset of the five fields. A supplied field is never re-derived: the model is shown it
as already agreed and drafts only what is missing, and the engine overwrites whatever the
model returns for a supplied field with what was supplied. A malformed supplied field, or an
unknown key, stops the run before any model call (exit 4) and names the field.

## Considered options

**Full contract only.** Rejected: grilling settles decisions and never produces a kill
criterion, so a full-only intake is unusable until the adapter solves that; the hybrid is
useful today.

**Drop a malformed field and draft a replacement, saying so in the log.** Rejected: that is
a silent discard of something a human wrote, the one bug class this project has sworn off,
and "said so in the log" is the promise that failed nine times in a week.

**Reject the whole file and run fully model-written.** Rejected: discards four good fields
for one bad one, and the run silently becomes the unattended kind the person was avoiding.

## Consequences

Provenance is per field (`scopeContract.provenance`), travels with the report, and is read by
the critic so a human-ratified assumption is not flagged as "a premise accepted instead of
tested". Every run writes the contract it used beside the report, so a re-run can hold
framing constant - the first controlled variable the panel has had.
