# Recorded runs

Raw output, kept so every number in the README can be checked rather than taken on
trust. Nothing here is cherry-picked; the failed and blocked runs are in here too.

## Two regimes, and they are not comparable

Everything with a `v2-` prefix was produced **after** 2026-09-06, with a local SearXNG
serving general-web results and with five instrument bugs fixed. Everything without the
prefix predates both, and is **superseded**.

The old runs are kept, not deleted, because they are the honest record of what the tool
did in the degraded regime, and because the before/after is itself a measurement. But
they should not be quoted as current numbers:

- **Search was scholarly-only.** All four general-web backends returned zero results on
  every one of them. Coverage gaps in those reports are a search artefact, not evidence
  that nothing exists. On the one question run under both regimes, sources went from 14
  to 26 and claims from 9 to 33.
- **Calibration ran on a biased sample.** The sampler took the first N of a rank-ordered
  list, so the subset was the strongest claims and skewed heavily toward survivors.
- **The strike policy never fired**, so `struckFromSummary` is empty in every one of
  them whatever the policy says.
- **`--calibrate` / `--sample-dropped` were reachable only by CLI flag.** A run that set
  the environment variables instead reported `calibration: null` with no explanation.
- Runs older than 2026-09-06 also have `hypothesisVerdicts: null`, because nothing after
  the framing phase read the contract yet.

## What the current regime measured

Six runs, `--calibrate 30 --sample-dropped 10`, 2026-09-06/07. Regenerate with
`python3 tools/compare_regimes.py`.

| Run | Kill rate | Citation acc | kappa | n | Gate |
|---|---|---|---|---|---|
| `v2-minimum-wage-employment` | 37% | 85.7% | 0.86 | 30 | **calibrated** |
| `v2-mammography-forties` | 17% | 82.9% | 0.71 | 30 | **calibrated** * |
| `v2-standing-desks` | 11% | 80.0% | 0.53 | 30 | usable but noisy |
| `v2-tdd-defect-rates` | 30% | 38.1% | 1.00 | 27 | underpowered |
| `v2-ai-water-per-query` | 52% | 61.9% | 0.79 | 21 | underpowered |
| `v2-nudge-publication-bias` | 17% | 90.0% | 0.75 | 12 | underpowered |

\* `v2-mammography-forties` hit a bug: synthesis failed, and the fallback return path
discarded the calibration and dropped-claim blocks that had already been computed and
logged. Both were recovered from `v2-mammography-forties.log` and re-inserted, flagged with
`recoveredFrom`. The per-lens table was not recoverable, so that `calibrated` verdict cannot
be re-checked against the per-lens precondition. The bug is fixed; no other run is affected.

`v2-nudge-publication-bias` ran while SearXNG had `qwant` enabled, which was returning
**fabricated** results — nonsense domains with gibberish titles, interleaved 1:1 with real
ones. Nothing fabricated was cited (the source picker rejected all of it), but it cost 11 of
15 source-picks and the run finished with 12 verified claims instead of 30. Treat its
numbers as compromised. Qwant is disabled from `v2-minimum-wage-employment` onward.

## The files

| Prefix | What it is |
|---|---|
| `v2-*` | Current regime: SearXNG on, all five fixes in, `--calibrate 30 --sample-dropped 10`. |
| `probes-*` | Injected-defect probe results for the citation auditor and the process critic. |
| `calibration-*` | Panel reliability runs, superseded — the first two are the ones the gate amendment was written against. |
| `*-BLOCKED-*` | A run that died on a server-side credential revocation. Kept because it is why `preflight()` exists. |
| everything else | Superseded regime. See above. |
