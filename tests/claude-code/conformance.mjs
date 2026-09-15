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

const DOC = JSON.parse(fs.readFileSync(here + '../../contract/conformance.json', 'utf8'))
const { cases, instruments } = DOC
const missing = Object.keys(cases).filter(f => !ADAPTER[f]).sort()
if (missing.length) {
  console.log('  GAP  contract names functions this runtime does not bind: ' + missing.join(', '))
  process.exit(1)
}

// THE STRUCTURAL RULE, applied to this build. A gate must have a `good` reference it
// accepts and a `bad` one it catches — and the bad references must produce at least one
// answer no good reference produces. A gate whose bad cases answer exactly what its good
// ones answer has not been shown to reject anything, however many cases it has. This is
// the rule the parity markers failed for years.
const want = c => ('out_by_runtime' in c ? c.out_by_runtime.js : c.out)
const structural = []
for (const fn of Object.keys(instruments).sort()) {
  if (!cases[fn]) continue                       // python-only; reported below, not failed
  if (instruments[fn] !== 'gate') continue
  const good = cases[fn].filter(c => c.ref === 'good')
  const bad = cases[fn].filter(c => c.ref === 'bad')
  if (!good.length) structural.push(fn + ': a gate with no `good` reference — nothing shows it accepts what it should')
  if (!bad.length) structural.push(fn + ': a gate with no `bad` reference — nothing shows it can reject at all')
  if (!good.length || !bad.length) continue
  const goodAnswers = new Set(good.map(c => JSON.stringify(want(c))))
  if (!bad.some(c => !goodAnswers.has(JSON.stringify(want(c))))) {
    structural.push(fn + ': every `bad` reference answers the same as a `good` one in THIS build, ' +
      'so this gate has never been observed to reject anything here')
  }
}
for (const s of structural) console.log('  STRUCTURE  ' + s)

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b)
let passed = 0, failed = structural.length
for (const fn of Object.keys(cases).sort()) {
  for (const c of cases[fn]) {
    const got = ADAPTER[fn](...c.in)
    if (eq(got, want(c))) { passed++; continue }
    failed++
    console.log('  FAIL  ' + fn + '(' + c.in.map(a => JSON.stringify(a).slice(0, 48)).join(', ') + ')')
    console.log('        expected ' + JSON.stringify(want(c)) + ', got ' + JSON.stringify(got))
    console.log('        ' + c.why)
  }
}
// Not a failure, but never silent: a gate this build genuinely does not have.
const pyOnly = Object.keys(DOC.python_cases || {}).sort()
if (pyOnly.length) {
  console.log('\n  Python-only gates, by design:')
  for (const fn of pyOnly) console.log('    - ' + fn.padEnd(20) + DOC.python_cases[fn].why_python_only.split('. ')[0].replace(/\.$/, '') + '.')
}
const gates = Object.values(instruments).filter(k => k === 'gate').length
console.log('\n  ======== conformance (js): ' + passed + ' passed, ' + failed + ' failed | ' +
  Object.keys(cases).length + ' instruments bound, ' + gates + ' gates declared, structure ' +
  (structural.length ? 'BROKEN' : 'sound') + ' ========')
process.exit(failed ? 1 : 0)
