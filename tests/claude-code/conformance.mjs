// Run contract/conformance.json against the JS build.
//
// The twin of tests/test_conformance.py, which asks the Python engine the identical
// questions. Neither runner owns an expected value: both read them from the contract, so
// a wrong answer the two builds happen to share still fails.
//
// Reaching the functions: the build is a Workflow script, not a module, so it exports
// nothing. Everything above `phase('Scope')` is definitions; below it is the run. This
// evaluates only the definitions and returns them. That split is why the hypothesis
// matcher was hoisted — it used to sit 900 lines inside the run, out of reach of any
// check that calls it directly, which is exactly where it drifted.
import fs from 'node:fs'

const here = new URL('.', import.meta.url).pathname
const SRC = fs.readFileSync(here + '../../integrations/claude-code/deepresearch.js', 'utf8')
  .replace(/^export const meta/m, 'const meta')
const SPLIT = SRC.indexOf("phase('Scope')")
if (SPLIT < 0) {
  console.log("  GAP  cannot find the definitions/run split (phase('Scope')) — has the pipeline moved?")
  process.exit(2)
}
const noop = () => {}
const M = new Function('agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget',
  '"use strict"; ' + SRC.slice(0, SPLIT) +
  '; return { shape, tierOf, asList, webText, hostIsAmbiguous, sameHyp, hypUnrelated, normHyp }')(
  noop, noop, noop, noop, noop, { question: 'conformance', depth: 'standard' }, {})

// The adapter: one entry per contract function. Return conventions differ between the
// builds on purpose (an object here, a tuple there); normalising them is this layer's
// whole job, and the only place a runtime-specific shape may appear.
const ADAPTER = {
  webtext:         (s, cap) => M.webText(s, cap === null ? undefined : cap),
  tier_of:         url => M.tierOf(url).tier,
  host_ambiguous:  url => M.hostIsAmbiguous(url),
  as_list:         v => M.asList(v, 'conformance'),
  same_hypothesis: (a, b) => M.sameHyp(M.normHyp(a), M.normHyp(b)),
  hyp_unrelated:   (a, b) => M.hypUnrelated(M.normHyp(a), M.normHyp(b)),
  shape_problems:  (schema, obj) => M.shape(schema, obj, 'conformance').problems.length,
}

const { cases } = JSON.parse(fs.readFileSync(here + '../../contract/conformance.json', 'utf8'))
const missing = Object.keys(cases).filter(f => !ADAPTER[f]).sort()
if (missing.length) {
  console.log('  GAP  contract names functions this runtime does not bind: ' + missing.join(', '))
  process.exit(1)
}
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b)
let passed = 0, failed = 0
for (const fn of Object.keys(cases).sort()) {
  for (const c of cases[fn]) {
    // `out_by_runtime` pins a DIFFERENT answer per build, for the cases where the
    // platform itself differs - URL parsing is the real one. Both answers are pinned,
    // so either moving is still a failure; it is not a way to excuse drift.
    const want = 'out_by_runtime' in c ? c.out_by_runtime.js : c.out
    const got = ADAPTER[fn](...c.in)
    if (eq(got, want)) { passed++; continue }
    failed++
    console.log('  FAIL  ' + fn + '(' + c.in.map(a => JSON.stringify(a).slice(0, 48)).join(', ') + ')')
    console.log('        expected ' + JSON.stringify(want) + ', got ' + JSON.stringify(got))
    console.log('        ' + c.why)
  }
}
for (const fn of Object.keys(ADAPTER).sort()) {
  if (!cases[fn]) console.log('  note  ' + fn + ' is bound here but has no cases in the contract')
}
console.log('\n  ======== conformance (js): ' + passed + ' passed, ' + failed + ' failed ========')
process.exit(failed ? 1 : 0)
