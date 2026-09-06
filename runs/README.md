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

## The files

| Prefix | What it is |
|---|---|
| `v2-*` | Current regime: SearXNG on, all five fixes in, `--calibrate 30 --sample-dropped 10`. |
| `probes-*` | Injected-defect probe results for the citation auditor and the process critic. |
| `calibration-*` | Panel reliability runs, superseded — the first two are the ones the gate amendment was written against. |
| `*-BLOCKED-*` | A run that died on a server-side credential revocation. Kept because it is why `preflight()` exists. |
| everything else | Superseded regime. See above. |
