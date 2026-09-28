import { run } from './simulate.mjs'
let pass = 0, fail = 0
const ok = (c, m) => { if (c) { pass++; console.log('  ✅ ' + m) } else { fail++; console.log('  ❌ FAIL: ' + m) } }

// ── T1: happy path, standard depth ────────────────────────────────────────
{
  const { out, logs, calls } = await run('T1 standard depth, happy path', { question: 'Does X cause Y?', depth: 'standard' })
  ok(out.depth === 'standard', 'depth resolved to standard')
  ok(out.stats.perspectives === 6, 'standard = 6 perspectives (got ' + out.stats.perspectives + ')')
  ok(out.stats.urlDupes >= 1, 'shared URL across 2 perspectives was deduped (dupes=' + out.stats.urlDupes + ')')
  ok(out.stats.subQuestions === 4, 'sub-question checklist carried through')
  ok(out.stats.lensesPerClaim === 3, 'standard uses 3 verification lenses')
  ok(out.stats.killed > 0, 'adversarial panel actually killed claims (' + out.stats.killed + ')')
  ok(out.stats.confirmed > 0, 'some claims survived (' + out.stats.confirmed + ')')
  ok(out.citationAudit !== null, 'citation audit ran at standard depth')
  ok(typeof out.citationAudit.citationAccuracy === 'number', 'citationAccuracy is a number: ' + out.citationAudit.citationAccuracy + '%')
  ok(out.citationAudit.supported + out.citationAudit.partial + out.citationAudit.unsupported + out.citationAudit.unreachable === out.stats.claimsVerified,
     'every VERIFIED claim got exactly one citation verdict (audit is independent of the panel, not downstream of it)')
  ok(out.stats.confirmed + out.stats.killed + out.stats.unverifiedCount === out.stats.claimsVerified,
     'claim accounting balances after demotion: confirmed + killed + unverified = verified')
  const j = out.citationAudit.supported + out.citationAudit.partial + out.citationAudit.unsupported
  ok(Math.abs(out.citationAudit.citationAccuracy - (out.citationAudit.supported / j) * 100) < 0.1,
     'citationAccuracy math correct, unreachable excluded from denominator')
  ok(out.processCritique.verdict === 'material-gaps', 'process critique takes the WORST verdict across critics')
  ok(out.processCritique.untraceableStatements.length > 0, 'critic surfaced untraceable summary statements')
  ok(out.coverage && out.coverage.length === 4, 'coverage checklist status returned')
  ok(out.contradictions.length >= 2, 'contradictions merged from gap analysis AND synthesis')
  ok(logs.some(l => l.includes('Round 1')), 'deepening round ran and logged')
  ok(out.sources.some(s => s.wave === 'w2'), 'follow-up wave sources present')
  ok(Object.keys(out.stats.killsByLens).length > 0, 'kills attributed per lens: ' + JSON.stringify(out.stats.killsByLens))
  console.log('  ℹ agent calls: ' + calls)
}

// ── T2: depth tiers ───────────────────────────────────────────────────────
{
  const q = await run('T2a quick', { question: 'Q', depth: 'quick' })
  ok(q.out.stats.perspectives === 4, 'quick CAPS an over-eager scoper (6 returned) down to 4 perspectives')
  ok(q.out.stats.lensesPerClaim === 3, 'quick runs all 3 lenses: with 2 and a 2-of-3 rule, a 1-1 split survives and nothing can ever be killed')
  ok(q.out.citationAudit === null, 'quick SKIPS the citation audit')
  ok(!q.logs.some(l => l.includes('Round 1')), 'quick does no deepening round')
  ok(q.out.processCritique.rationales.length === 1, 'quick = 1 process critic')

  const e = await run('T2b exhaustive', { question: 'Q', depth: 'exhaustive' })
  ok(e.out.stats.perspectives === 6, 'exhaustive keeps all 6 (under its cap of 9)')
  ok(e.out.processCritique.rationales.length === 3, 'exhaustive = 3 process critics')
  ok(e.calls > q.calls, 'exhaustive spends more agents than quick (' + e.calls + ' vs ' + q.calls + ')')
  console.log('  ℹ agents — quick:' + q.calls + '  exhaustive:' + e.calls)
}

// ── T3: args parsing ──────────────────────────────────────────────────────
{
  const a = await run('T3a bare string', 'just a question string')
  ok(a.out.depth === 'standard', 'bare string defaults to standard depth')
  ok(a.out.question === 'just a question string', 'bare string used as question')

  const b = await run('T3b prefixed string', 'exhaustive: what is the thing?')
  ok(b.out.depth === 'exhaustive', 'prefix "exhaustive:" parsed as depth')
  ok(b.out.question === 'what is the thing?', 'prefix stripped from question')

  const c = await run('T3c bad depth', { question: 'Q', depth: 'turbo' })
  ok(c.out.depth === 'standard', 'unknown depth falls back to standard, not crash')

  const d = await run('T3d empty', { question: '   ' })
  ok(!!d.out.error, 'empty question returns a clean error, not a crash')
}

// ── T4: security — host labels must never spoof ───────────────────────────
{
  const { labels } = await run('T4 host label spoofing', { question: 'Q', depth: 'quick' })
  const fetchLabels = labels.filter(l => l.startsWith('fetch:'))
  const spoof = fetchLabels.find(l => l.includes('trusted.org') && !l.includes('"'))
  ok(!spoof, 'backslash-userinfo URL never renders as a bare trusted.org label')
  const idn = fetchLabels.find(l => /аmazon/.test(l))
  ok(!idn || idn.includes('"'), 'IDN homograph host is quoted, never bare')
  console.log('  ℹ fetch labels: ' + fetchLabels.join('  |  '))
}

// ── T5: failure paths must degrade, not crash ─────────────────────────────
{
  const a = await run('T5a all verifiers die', { question: 'Q', depth: 'standard' }, { allVerifiersDie: true })
  ok(a.out.findings.length === 0, 'no findings when every verifier errors')
  ok(/INFRASTRUCTURE FAILURE/.test(a.out.summary), 'infra failure is NOT reported as "research found nothing"')

  const b = await run('T5b every fetch empty', { question: 'Q', depth: 'standard' }, { emptyFetch: true })
  ok(b.out.stats.claimsExtracted === 0, 'zero claims extracted')
  ok(b.out.findings.length === 0 && !!b.out.summary, 'empty run returns a clean summary, not a crash')

  const c = await run('T5c synthesis fails', { question: 'Q', depth: 'standard' }, { noSynth: true })
  ok(c.out.confirmedRaw && c.out.confirmedRaw.length > 0, 'synthesis failure SALVAGES verified claims instead of discarding the run')

  const d = await run('T5d gap analyst finds no gaps', { question: 'Q', depth: 'standard' }, { noFollowUps: true })
  ok(d.logs.some(l => l.includes('Coverage complete')), 'stops deepening early when coverage is complete')
  ok(!d.out.sources.some(s => s.wave === 'w2'), 'no wasted follow-up wave when there are no gaps')
}


// ══════════ NEW TESTS: fixes driven by the live end-to-end run ══════════
import { SQ } from './simulate.mjs'
import fsCap from 'node:fs'
{
  const { out, logs } = await run('T6 coverage-balanced claim selection', { question: 'Q', depth: 'standard' })
  const capSrc = fsCap.readFileSync(new URL('../../integrations/claude-code/deepresearch.js', import.meta.url).pathname,'utf8')
  const caps = Object.fromEntries([...capSrc.matchAll(/(quick|standard|exhaustive):\s*\{[^}]*maxVerify:\s*(\d+)/g)].map(m=>[m[1],+m[2]]))
  // Checked against contract/depths.json, NOT against a number typed here. This
  // assertion used to read `caps.quick === 14` — written against this build's own copy
  // rather than the shared budget — so the JS suite actively certified the drift:
  // quick verified 14 claims here and 10 in the Python engine, 42 agent calls against
  // 30 for the same requested depth, green in both suites the whole time.
  const DEPTHS = JSON.parse(fsCap.readFileSync(new URL('../../contract/depths.json', import.meta.url).pathname, 'utf8')).depths
  const mismatch = Object.keys(DEPTHS).filter(d => caps[d] !== DEPTHS[d].max_verify)
  ok(mismatch.length === 0,
     'verify budgets come from contract/depths.json: quick=' + caps.quick + ' standard=' + caps.standard +
     ' exhaustive=' + caps.exhaustive + (mismatch.length ? ' — DRIFTED at: ' + mismatch.join(', ') : ''))
  ok(out.stats.claimsVerified === Math.min(out.stats.claimsExtracted, caps.standard),
     'every extracted claim verified when under cap (' + out.stats.claimsVerified + '/' + out.stats.claimsExtracted + ', cap ' + caps.standard + ')')
  ok(out.stats.claimsDroppedBeforeVerify === Math.max(0, out.stats.claimsExtracted - caps.standard),
     'drop count is accurate and reported, never silent')
  ok(logs.some(l => /Verify pool spans [2-9] distinct sub-question buckets/.test(l)),
     'verify pool spans MULTIPLE sub-question buckets — one topic cannot eat the whole budget')
  console.log('  ℹ ' + logs.find(l => l.includes('Verify pool spans')))
}
{
  // Kill every claim tagged SQ3 -> that sub-question is wiped -> rescue must fire.
  const { out, logs } = await run('T7 rescue fires on a wiped-out sub-question',
    { question: 'Q', depth: 'standard' }, { wipeSubQuestion: SQ[2], rescueTarget: SQ[2], rescueIndex: 3 })
  ok(!!out.rescue, 'rescue block ran')
  ok(logs.some(l => l.startsWith('RESCUE:')), 'rescue logged loudly')
  ok(out.rescue.targeted > 0, 'rescue targeted ' + out.rescue.targeted + ' wiped sub-question(s)')
  ok(out.rescue.sourcesAdded > 0, 'rescue pulled ' + out.rescue.sourcesAdded + ' NEW primary sources')
  ok(out.rescue.claimsSaved > 0, 'rescue RECOVERED ' + out.rescue.claimsSaved + ' claim(s) that would otherwise be lost')
  ok(out.sources.some(s => s.wave === 'rescue'), 'rescue sources tagged and merged into the source list')
  console.log('  ℹ ' + logs.filter(l => l.startsWith('RESCUE:')).join(' | '))
}
{
  const { out } = await run('T8 rescue disabled at quick depth', { question: 'Q', depth: 'quick' }, { wipeSubQuestion: SQ[2] })
  ok(out.rescue === null || out.rescue === undefined, 'quick depth does NOT run the rescue pass')
}
{
  const { out, logs } = await run('T9 rescue finds nothing', { question: 'Q', depth: 'standard' },
    { wipeSubQuestion: SQ[2], emptyFetch: true })
  ok(logs.some(l => /remain genuinely unanswered|no new claims/i.test(l)) || out.findings.length === 0,
     'rescue that finds nothing says so rather than faking coverage')
}
{
  const { out } = await run('T10 steelman + constructor mandated in scope prompt', { question: 'Q', depth: 'standard' })
  ok(out.stats.perspectives === 6, 'scope still returns a capped perspective set')
}
import fs2 from 'node:fs'
{
  const src = fs2.readFileSync(new URL('../../integrations/claude-code/deepresearch.js', import.meta.url).pathname, 'utf8')
  ok(/Mandatory steelman/.test(src), 'scope prompt contains the mandatory-steelman instruction')
  ok(/Mandatory constructor/.test(src), 'scope prompt contains the mandatory-constructor instruction')
}


// ══════════ FIX 6: citation audit must be an independent filter ══════════
{
  const { out, logs } = await run('T11 audit scores the FULL pool and can demote', { question: 'Q', depth: 'standard' })
  ok(out.citationAudit.supported + out.citationAudit.partial + out.citationAudit.unsupported + out.citationAudit.unreachable
       === out.stats.claimsVerified,
     'audit now covers EVERY verified claim (' + out.citationAudit.supported + '+' + out.citationAudit.partial + '+' +
     out.citationAudit.unsupported + '+' + out.citationAudit.unreachable + ' = ' + out.stats.claimsVerified + '), not just survivors')
  ok(out.citationAudit.citationAccuracy < 100,
     'accuracy is now a REAL varying number, not a rubber stamp: ' + out.citationAudit.citationAccuracy + '%')
  ok(out.citationAudit.unsupported > 0, 'unsupported citations are actually detected (' + out.citationAudit.unsupported + ')')
  ok(typeof out.citationAudit.demotedBySurvivingPanel === 'number', 'demotion count reported')
  ok(logs.some(l => l.startsWith('AUDIT DEMOTED')), 'demotion logged loudly')
  ok(out.refuted.some(r => /citation-audit/.test(r.killedBy || '')),
     'demoted claims appear in `refuted` attributed to citation-audit, not silently dropped')
  console.log('  ℹ ' + logs.filter(l => /Citation audit|AUDIT DEMOTED/.test(l)).join('\n  ℹ '))
}

// ══ FIX 7: audit must cover claims the RESCUE pass added (found in live run 3) ══
{
  const { out } = await run('T12 rescue claims are citation-audited too',
    { question: 'Q', depth: 'standard' }, { wipeSubQuestion: SQ[2], rescueTarget: SQ[2], rescueIndex: 3 })
  const audited = out.citationAudit.supported + out.citationAudit.partial + out.citationAudit.unsupported + out.citationAudit.unreachable
  ok(out.rescue && out.rescue.claimsReVerified > 0, 'rescue ran and re-verified claims')
  ok(audited === out.stats.claimsVerified,
     'EVERY verified claim is audited, rescue-added ones included (' + audited + ' audited / ' + out.stats.claimsVerified + ' verified)')
}
// ══ ported mega_research features + the seam guard ══
{
  const { out } = await run('T13 scope split, guard, tiering', { question: 'Q', depth: 'standard' })
  ok(!!out.scopeContract && out.scopeContract.keyQuestion === 'k', 'framing contract carried into the report')
  ok(out.scopeContract.hypotheses.length === 2, 'hypotheses with kill criteria present')
  ok(!!out.answerFirst, 'answerFirst present (Pyramid Principle)')
  ok(!!out.strongestArgumentAgainst, 'strongestArgumentAgainst is required and present')
  ok(Array.isArray(out.whatWouldChangeThisCall), 'whatWouldChangeThisCall present')
  ok(out.findings[0].factOrInference === 'fact', 'findings tag fact vs inference')
  ok(!!out.stats.sourceTiers, 'tier census in stats: ' + JSON.stringify(out.stats.sourceTiers))
}
{
  const { out, logs } = await run('T14 subQuestions as a STRING', { question: 'Q', depth: 'standard' }, { plan_string_subq: true })
  ok(!!out.error, 'string-where-list-expected is rejected, not iterated into fake items')
  ok(logs.some(l => /\[plan[^\]]*\] response violates its own schema: subQuestions=0/.test(l)),
     'the SEAM names the violation (subQuestions=0, schema requires 3) before any caller sees it')
}
{
  const { out } = await run('T15 framing failure is survivable', { question: 'Q', depth: 'standard' }, { no_framing: true })
  ok(!out.error, 'a failed framing no longer kills the run')
}
{
  const { out } = await run('T16 <UNKNOWN> sentinel is retried, not surfaced', { question: 'Q', depth: 'standard' }, { unknown_sentinel_once: true })
  ok(!out.error, 'a transient <UNKNOWN> sentinel is retried away rather than failing the run')
  ok(out.stats.confirmed > 0, 'and the run completes normally afterwards')
}
{
  const { out } = await run('T17 parity with the python engine', { question: 'Q', depth: 'standard' })
  ok(Array.isArray(out.hypothesisVerdicts) && out.hypothesisVerdicts.length === 2,
     'hypotheses are adjudicated here too, not just in the python build (#6)')
  ok(out.hypothesisVerdicts.some(h => h.verdict === 'untested'),
     'untested is a first-class verdict')
  ok(out.honestLimits && out.honestLimits.falseKillRateUnmeasured,
     'honestLimits travel with the JS report as well (#12)')
  ok(out.honestLimits.evidenceBase && typeof out.honestLimits.evidenceBase.citableSources === 'number',
     'and the evidence base is COUNTED in a real report, not just present in the source: ' +
     JSON.stringify(out.honestLimits.evidenceBase.citableSources))
  ok(out.processCritique.policy === 'flag' && Array.isArray(out.processCritique.struckFromSummary),
     'strike/flag policy is present and defaults to flag (#4)')
  // Stamped, and stamped with HOW it was decided. This used to be asserted by matching a
  // line of source text, which is the same instrument that certified `hypothesisNumber`
  // as present in this build when its only occurrence was a comment claiming so.
  ok(out.hypothesisVerdicts.every(h => h.preRegistered === true &&
                                       /^hypothesisNumber \(/.test(h.preRegisteredBy)),
     'every verdict is stamped pre-registered BY the number it declared, so a reader can tell a certainty from a guess')
}
{
  // The dropped-claim sample, which was PYTHON_ONLY until now: "portable in principle,
  // not yet ported". The Python twin has measured it twice and the answer is awkward -
  // 10/10 dropped claims survived against 80% of kept, and 8/10 against 83%. A number
  // that uncomfortable should not depend on which runtime you happened to run.
  // `quick` caps verification at 10 and the simulation yields 18 citable claims, so the
  // cap actually bites here. At `standard` (cap 30) nothing is dropped — which is the
  // mirror case, checked below.
  const { out, logs } = await run('T17f the cap is measured, not assumed',
    { question: 'Q', depth: 'quick', sampleDropped: 3 })
  ok(out.droppedSample && out.droppedSample.sampled > 0,
     'claims the verify cap discarded are sampled and put through the panel')
  ok(typeof out.droppedSample.survivalRate === 'number' &&
     typeof out.droppedSample.keptClaimSurvivalRate === 'number',
     'and BOTH rates are published, because one without the other says nothing: ' +
     out.droppedSample.survivalRate + ' vs ' + out.droppedSample.keptClaimSurvivalRate)
  ok(/not selecting for verifiability|materially different rate/.test(out.droppedSample.reading || ''),
     'with a reading that states which of the two it is, rather than leaving the reader to subtract')
  ok(logs.some(l => /dropped claims survived/.test(l)), 'and it is logged as it happens')
  // Both builds took a PREFIX of the dropped pool for three versions while the Python
  // comment said "random-ish" (review of 1.18.2, 2026-09-28). The draw is now uniform
  // and the per-claim rows are the record of it - the aggregate alone cannot be audited.
  ok(Array.isArray(out.droppedSample.claims) &&
     out.droppedSample.claims.length === out.droppedSample.sampled &&
     out.droppedSample.claims.every(r => r.claim && typeof r.survived === 'boolean'),
     'each sampled claim rides with the report, so the draw is its own record')
  ok(/not measured/.test(out.droppedSample.measures || ''),
     'and the report says survival is measured, materiality (#9) is not')

  // The mirror: when the cap discarded NOTHING, no rate is invented. A survival rate
  // over an empty pool would be a number with no measurement behind it.
  const none = await run('T17g nothing dropped means nothing claimed',
    { question: 'Q', depth: 'standard', sampleDropped: 3 })
  ok(none.out.droppedSample === null || none.out.droppedSample === undefined,
     'with 18 claims under a cap of 30 nothing is discarded, so no sample is published')
}
{
  // A mandatory field that points at itself. Four of the Python build's 20 recorded runs
  // published a `strongestArgumentAgainst` cross-referencing the field itself, and in
  // none of them does the argument exist anywhere else in the report. This build runs
  // the same synthesis rule, so it gets the same check rather than a comment saying it
  // would probably be fine.
  const { out, logs } = await run('T17d a self-referential mandatory field is re-asked, then disclosed',
    { question: 'Q', depth: 'standard' }, { pointer_steelman: true })
  ok(logs.some(l => /came back as a cross-reference/.test(l)),
     'the pointer is detected and named in the log, not accepted as content')
  ok(/one university/.test(out.strongestArgumentAgainst || ''),
     'ONE more call is made for that field alone and the argument is recovered')
  ok(!(out.honestLimits || {}).noSteelman,
     'with no false alarm in honestLimits when the recovery worked')

  const hard = await run('T17e a re-ask that also points is disclosed, not published',
    { question: 'Q', depth: 'standard' }, { pointer_steelman_hard: true })
  ok(/NOT PRODUCED/.test(hard.out.strongestArgumentAgainst || ''),
     'when the re-ask ALSO returns a pointer the field says so plainly')
  ok((hard.out.honestLimits || {}).noSteelman,
     'and the limit travels with the report, so the reader sees the conclusion stands unopposed')
}
{
  // The attack, run on THIS build rather than only on the Python one: a verdict
  // adjudicating a hypothesis the run never registered, declaring H1 anyway.
  const { out } = await run('T17b a declared hypothesisNumber is checked, not believed',
    { question: 'Q', depth: 'standard' }, { misnumbered_verdict: true })
  const bogus = out.hypothesisVerdicts.find(h => /decade-long/.test(h.hypothesis))
  const real = out.hypothesisVerdicts.find(h => /publication-selection/.test(h.hypothesis))
  ok(bogus && bogus.preRegistered === false,
     'a verdict whose text was never registered is NOT stamped pre-registered just because it typed a digit')
  ok(bogus && /^inferred from text/.test(bogus.preRegisteredBy) && /H1/.test(bogus.preRegisteredBy),
     'and the stamp says the number was overruled and which one it claimed: ' + (bogus && bogus.preRegisteredBy))
  ok(real && real.preRegistered === true && /^hypothesisNumber \(/.test(real.preRegisteredBy),
     'while a verdict that really does adjudicate its numbered hypothesis is still believed, relabelled or not')
}
{
  // The string leaf. `required` only ever meant key-present, so the locatedQuote fix was
  // hollow in THIS build: a number passed the schema exactly as a real quote did, and the
  // commit that closed it in Python reported "now enforced in both builds".
  const { out, logs } = await run('T17c a declared string rejects a number at the seam',
    { question: 'Q', depth: 'standard' }, { string_leaf_violation: true })
  ok(logs.some(l => /locatedQuote is a number, not a string/.test(l)),
     'a number where a string is declared is a schema violation, named in the log')
  ok(logs.some(l => /locatedQuote is a number, not a string.*retrying/.test(l)),
     'and the seam RETRIES it rather than coercing or dropping it (ADR-0001)')
  ok(out.citationAudit.auditErrors > 0,
     'the calls that never recovered are COUNTED, not filtered away into a smaller denominator (' + out.citationAudit.auditErrors + ')')
}
{
  const { out, logs } = await run('T18 an empty framing contract is retried, not accepted (#16)',
    { question: 'Q', depth: 'standard' }, { short_framing_once: true })
  ok(logs.some(l => l.includes('violates its own schema')),
     'zero assumptions and zero hypotheses is caught as a schema violation, not read as an answer')
  ok(logs.some(l => l.includes('hypotheses=0')),
     'and the log names the offending array, so the next reader is not debugging blind')
  ok(Array.isArray(out.hypothesisVerdicts) && out.hypothesisVerdicts.length === 2,
     'the retry recovers a real contract, so hypotheses are adjudicated after all')
  ok(!out.error, 'and the run completes normally')
}
{
  const { out, logs } = await run('T19 calibration: balanced sample, degeneracy guard, amended gate',
    { question: 'Q', depth: 'standard', calibrate: 12 })
  const c = out.calibration
  ok(c && typeof c.n === 'number', 'calibration ran and produced a block (n=' + (c && c.n) + ')')
  ok(c && c.perLens && Object.keys(c.perLens).length >= 2,
     'per-lens agreement is computed, so a dominant lens cannot hide behind the aggregate')
  ok(c && c.lensSplit && typeof c.lensSplit.disagreementRate === 'number',
     'lens split rate is reported alongside (' + (c && c.lensSplit.disagreementRate) + ')')
  ok(c && typeof c.gateVerdict === 'string',
     'the pre-registered gate returns a verdict here too, not just in python: ' + (c && c.gateVerdict))
  ok(c && c.thresholds.minimumN === 30 && c.thresholds.minimumPerLensKappa === 0.4,
     'the amended preconditions travel inside the report')
  ok(c && (c.cohenKappa === null ? c.degenerate === true : true),
     'a near-degenerate matrix reports undefined rather than a confident-looking zero')
  ok(c && (c.n < 30 ? c.gateVerdict === 'underpowered' : true),
     'and n below 30 returns underpowered whatever the coefficient says')
  ok(logs.some(l => l.includes('CALIBRATION')), 'and it says so in the log')
}
{
  const sup = { keyQuestion: 'do standing desks improve health?', assumptions: ['office workers', '12 months'],
                whatWouldChangeTheAnswer: ['an RCT showing harm', 'no effect'], decisionAtStake: 'buy 40 desks',
                needsGeneralWeb: false }
  const { out, logs } = await run('T20 contract intake: supplied fields win, the model drafts the rest',
    { question: 'Q', depth: 'standard', contract: sup })
  ok(out.scopeContract && out.scopeContract.keyQuestion === sup.keyQuestion, 'a supplied field reaches the report verbatim')
  ok(out.scopeContract.provenance && out.scopeContract.provenance.assumptions === 'supplied' && out.scopeContract.provenance.hypotheses === 'drafted',
     'provenance is per field: ' + JSON.stringify(out.scopeContract.provenance))
  ok(logs.some(l => /Contract: 5 field\(s\) supplied/.test(l)), 'the log names what was supplied')
  ok(Array.isArray(out.hypothesisVerdicts) && out.hypothesisVerdicts.length === 2, 'drafted hypotheses are still adjudicated')
  const bad = await run('T20b malformed supplied field is rejected before any model call',
    { question: 'Q', depth: 'standard', contract: { assumptions: 'one prose string' } })
  ok(bad.out.error && /contract rejected/.test(bad.out.error) && /assumptions/.test(bad.out.error), 'named, not dropped: ' + bad.out.error)
  const drop = await run('T20d a dropped supplied item is rejected', { question: 'Q', depth: 'standard',
    contract: { hypotheses: [{ hypothesis: 'h1', killCriterion: 'k1' }, { hypothesis: 'h2', killCriterion: 'k2' }, { hypothesis: 'h3 no kill criterion' }] } })
  ok(drop.out.error && /3 item\(s\) and 2 survived/.test(drop.out.error),
     'a supplied item is never dropped even when survivors meet minItems: ' + drop.out.error)
  const typo = await run('T20c unknown key is rejected', { question: 'Q', depth: 'standard', contract: { assumption: ['x'] } })
  ok(typo.out.error && /unknown field/.test(typo.out.error), 'a typo is not silently honoured: ' + typo.out.error)
  ok(typo.calls === 0 && bad.calls === 0, 'and neither spent a single agent call')
}
{
  // Effect, not presence — the Python twin of this test passed while the rule was ignored.
  const sup = { keyQuestion: 'k', assumptions: ['a', 'b'], whatWouldChangeTheAnswer: ['w', 'x'],
                decisionAtStake: 'd', hypotheses: [{ hypothesis: 'h1', killCriterion: 'k1' }, { hypothesis: 'h2', killCriterion: 'k2' }],
                needsGeneralWeb: true }
  const { logs: L1 } = await run('T21 fully ratified framing: no untested-premise hunt', { question: 'Q', depth: 'standard', contract: sup })
  ok(L1.some(l => /nothing to draft/.test(l)), 'a fully supplied contract drafts nothing')
  const { out } = await run('T21b provenance reaches the report', { question: 'Q', depth: 'standard', contract: sup })
  ok(out.scopeContract.provenance && Object.values(out.scopeContract.provenance).every(v => v === 'supplied'),
     'every field reads supplied: ' + JSON.stringify(out.scopeContract.provenance))
}
{
  // The four early exits used to carry NO honestLimits at all, while the parity marker
  // check passed because the string existed on the happy path. Assert the effect.
  const fs3 = await import('node:fs')
  const src = fs3.readFileSync(new URL('../../integrations/claude-code/deepresearch.js', import.meta.url).pathname, 'utf8')
  // Every path that returns a report calls sourceRows(); every one must also build
  // the limits. Comparing the two counts catches a new exit added without them.
  const nExits = (src.match(/sources: sourceRows\(\)/g) || []).length
  const nLimits = (src.match(/honestLimits: honestLimits\(/g) || []).length
  ok(nExits === nLimits && nExits === 5,
     'every one of the ' + nExits + ' report exits builds honestLimits (' + nLimits + ' do)')
  ok(/honestLimits: honestLimits\(\)/.test(src) && !/honestLimits: \{/.test(src),
     'there is ONE honestLimits builder, so a caveat cannot be added to one exit and missed on the others')
  // `evidenceBase(allSources)`, not `evidenceBase()`. It used to close over the run's
  // sources and take nothing, which left contract/conformance.json unable to ask the one
  // instrument that decides whether a report is labelled THIN anything at all.
  ok(/evidenceBase: evidenceBase\(allSources\)/.test(src) && /MIN_CITABLE_SOURCES = 5/.test(src),
     'every exit reports how many citable sources the report rests on, from rows PASSED to it')
  // Must reuse s.tier, the value computed at fetch time and censused by
  // stats.sourceTiers. Recomputing from the URL alone made a report disagree with
  // itself about one source's tier once already.
  ok(/CITABLE\.has\(s\.tier \|\| 'T3'\)/.test(src) && /const c = \{\}[\s\S]{0,200}s\.tier/.test(src),
     'the citable count and the tier census read the same fetch-time tier, so one report cannot disagree with itself')
  // The auditor is asked for locatedQuote on every call; for months nothing read it.
  ok(/locatedQuote: webText\(f\.locatedQuote/.test(src),
     'the auditor\'s own verbatim pull is published rather than demanded and discarded')
  // The synthesis model can invent hypotheses AFTER seeing the evidence and adjudicate
  // them; the caveat beside the field used to assert the field was empty.
  ok(/NOTHING here was pre-registered/.test(src) && /postHocHypotheses/.test(src),
     'and the no-contract caveat describes what the field actually holds instead of asserting it is empty')
  // as_list recovering a payload that shape() then discards was the defect that killed
  // framing on a live run while holding all four hypotheses.
  ok(/bareItems\.length && !lst\.length/.test(src),
     'a wasted tag-recovery triggers an INFORMED re-ask, and only when nothing survived')
  ok(/each item must be an OBJECT with the keys/.test(src),
     'and the re-ask names the recovered text and the required keys, so it is not the identical question again')
  ok(/refutedBy: refuters\.map/.test(src) && /contradictedBy: refuters/.test(src),
     'a killed claim lists every refuter and every named counter-source: `why` used to be '
     + 'the first refuter only, and counterSource was demanded on every counter call and read by nothing')
  // WEB_STRIP is built from \p{...} property escapes, meaningless without the 'u' flag.
  ok(/return new RegExp\(out, 'u'\)/.test(src),
     'the tolerant strike pattern is compiled in unicode mode, or its character classes are nonsense')
  // The match now lives in flagSpans, the one locator annotate and strike share.
  ok(/new RegExp\(webTextPattern\(frag\)\.source, 'gu'\)/.test(src) && !/text\.includes\(frag\)/.test(src),
     'the strike matches through webText, not with a plain includes() that misses on any summary containing a quotation mark')
  ok((src.match(/const toRefuted =/g) || []).length === 1,
     'exactly one toRefuted builder - the Python twin had TWO, and fixing one left the happy path on the old shape')
  ok(!/citableSources < MIN_CITABLE_SOURCES\) return/.test(src) && /NOT aborted for being thin/.test(src),
     'a thin run is labelled, never aborted: the thinnest run on record was thin because of a bug, and aborting would have hidden it')
}
// ══════════ Review 2026-09-27: defects a whole-codebase review proved in this build ══════════
// Each was reproduced with this harness before it was fixed; none was visible to the suite.
{
  // A bare hyphen counted as a depth separator, so a compound first word was eaten.
  const a = await run('R1a compound first word', { question: 'Quick-service restaurant margins in 2026?', depth: 'exhaustive' })
  ok(a.out.question === 'Quick-service restaurant margins in 2026?' && a.out.depth === 'exhaustive',
     '"Quick-service ..." is a question, not a quick-depth prefix (got ' + JSON.stringify(a.out.question) + ')')
  const b = await run('R1b spaced dash prefix', 'quick - what is the thing?')
  ok(b.out.depth === 'quick' && b.out.question === 'what is the thing?', 'a spaced dash is still a prefix')
}
{
  // agent() THROWS when a token budget is spent. Uncaught at synthesis, the whole run
  // rejected and the fallback that keeps verified claims and calibration never ran.
  let threw = null, r = null
  try { r = await run('R2 agent throws at synthesis', { question: 'Q', depth: 'standard' }, { throwAt: 'synthesize' }) }
  catch (e) { threw = e.message }
  ok(!threw && r.out.confirmedRaw && r.out.confirmedRaw.length > 0,
     'a thrown agent call is a failed call: the run returns its verified claims (' + (threw || 'no throw escaped') + ')')
  ok(r && r.logs.some(l => /agent call threw/.test(l)), 'and the throw is logged, not swallowed')
}
{
  // The rescue pool skipped citableOnly: a T5 rescue source reached the panel and
  // could land in the confirmed findings.
  const { out } = await run('R3 rescue excludes non-citable sources', { question: 'Q', depth: 'standard' },
    { wipeSubQuestion: SQ[2], rescueTarget: SQ[2], rescueIndex: 3, farmRescue: true })
  ok(out.rescue && out.rescue.sourcesAdded >= 2, 'the farm and the primary rescue sources were both read')
  ok(!(out.citationDetail || []).some(r => /buzzfeed/.test(r.url)) && !(out.refuted || []).some(r => /buzzfeed/.test(r.source)),
     'no claim from a T5 rescue source reached the panel or the audit')
}
{
  // The all-demoted exit dropped calibration, the dropped sample, citationDetail and
  // scopeContract, and a demoted claim's `why` was empty (the panel passed it).
  const { out } = await run('R4 audit demotes every survivor', { question: 'Q', depth: 'standard', calibrate: 4 },
    { cite_all_unsupported: true })
  ok(/demoted by the blind citation audit/.test(out.summary || ''), 'the all-demoted exit is reached')
  ok('calibration' in out && 'droppedSample' in out && (out.citationDetail || []).length > 0 && out.scopeContract,
     'and it carries calibration, droppedSample, citationDetail and scopeContract')
  const dem = (out.refuted || []).filter(r => /citation-audit/.test(r.killedBy))
  ok(dem.length > 0 && dem.every(r => r.why), 'a demoted claim says WHY: the audit\'s reasoning, not an empty string')
}
{
  // {claim, url, ...f} let the model's echo overwrite the row: an unsupported verdict
  // stopped matching its claim and demotion silently stopped.
  const { out } = await run('R5 auditor echoes claim/url', { question: 'Q', depth: 'standard' }, { cite_echo_keys: true })
  ok(out.stats.confirmed === 0 && (out.citationDetail || []).every(r => r.url !== 'https://echoed.example/'),
     'the engine\'s claim/url win over an echo, so unsupported still demotes (confirmed=' + out.stats.confirmed + ')')
}
{
  // Restate-or-drop, ported from the Python twin: a partial SURVIVOR is restated and
  // re-audited. Supported swaps in the weakened claim; still-partial demotes.
  const a = await run('R6a restate succeeds', { question: 'Q', depth: 'standard' })
  ok(a.labels.some(l => l.startsWith('restate:')) && a.out.citationAudit.restatedToSupported > 0,
     'partial survivors are restated and re-audited (' + a.out.citationAudit.restatedToSupported + ' restated)')
  ok((a.out.citationDetail || []).some(r => r.restatedFrom),
     'a restated row keeps the original wording in restatedFrom')
  const b = await run('R6b restate fails', { question: 'Q', depth: 'standard' }, { restate_fails: true })
  ok(b.out.citationAudit.demotedBySurvivingPanel > a.out.citationAudit.demotedBySurvivingPanel,
     'a restatement that is still partial DEMOTES (' + b.out.citationAudit.demotedBySurvivingPanel + ' vs ' +
     a.out.citationAudit.demotedBySurvivingPanel + ' demoted)')
}
{
  // The report's coverage was the gap analyst's PRE-panel table: a sub-question whose
  // every claim died still read "answered". SQ1 is "answered" in the stub; kill it.
  const { out } = await run('R7 coverage reconciled after the panel', { question: 'Q', depth: 'standard' },
    { wipeSubQuestion: SQ[0], rescueTarget: SQ[2], rescueIndex: 3 })
  const row = (out.coverage || []).find(c => c.subQuestion === SQ[0])
  ok(row && row.status === 'killed-in-verification', 'a sub-question whose claims all died reads killed-in-verification (' + (row && row.status) + ')')
}
{
  // Every exit carries the contract and the same unverified key; the limits say what ran.
  const a = await run('R8a not-ranked exit', { question: 'Q', depth: 'standard' }, { emptyFetch: true })
  ok(a.out.scopeContract && a.out.scopeContract.provenance, 'the not-ranked exit carries scopeContract')
  const b = await run('R8b all verifiers die', { question: 'Q', depth: 'standard' }, { allVerifiersDie: true })
  ok('unverifiedCount' in b.out.stats && !('unverified' in b.out.stats) && b.out.scopeContract,
     'the all-refuted exit uses stats.unverifiedCount like every other exit, and carries scopeContract')
  const q = await run('R8c quick', { question: 'Q', depth: 'quick' })
  ok(q.out.honestLimits.citationAuditOff, 'quick depth SAYS no citation was re-checked')
  const s = await run('R8d standard', { question: 'Q', depth: 'standard' })
  ok(String(s.out.honestLimits.evidenceChecked || '').startsWith(s.out.stats.claimsVerified + ' of '),
     'evidenceChecked counts the claims actually verified (' + String(s.out.honestLimits.evidenceChecked).slice(0, 30) + ')')
  ok(!/stats\.searchHealth/.test(s.out.honestLimits.searchCoverage), 'searchCoverage no longer points at a field this build never has')
}
{
  // Synthesis was told "N lower-ranked claims were never verified" counted against
  // rankedClaims, which never holds rescue claims, and the second disclosure fired only
  // at >=50% while describing a tier-first ranking.
  const { out, prompts } = await run('R9 one honest never-verified disclosure', { question: 'Q', depth: 'standard' },
    { wipeSubQuestion: SQ[2], rescueTarget: SQ[2], rescueIndex: 3, farmRescue: true })
  const syn = (prompts.find(p => p.label === 'synthesize') || {}).prompt || ''
  const never = out.stats.claimsExtracted - out.stats.claimsVerified
  ok(never > 0 && syn.includes(never + ' of ' + out.stats.claimsExtracted + ' extracted claims'),
     'the disclosure uses the final pools (' + never + ' of ' + out.stats.claimsExtracted + ')')
  ok(!/source tier first/.test(syn) && /importance first/.test(syn), 'and describes the importance-first ranking')
  const src = fsCap.readFileSync(new URL('../../integrations/claude-code/deepresearch.js', import.meta.url).pathname, 'utf8')
  ok(!/DROP_PCT >= 50/.test(src), 'no threshold gates the disclosure')
}
{
  // A curly apostrophe hid the negator: "don’t" tokenised as "don" + "t", so an
  // opposite verdict stamped preRegistered with the certainty label.
  const { out } = await run('R10 curly-apostrophe negation', { question: 'Q', depth: 'standard' }, { curly_negation: true })
  const v = (out.hypothesisVerdicts || []).find(x => x.hypothesisNumber === 1)
  ok(v && v.preRegistered === false, 'a verdict that negates H1 with a curly apostrophe is NOT stamped pre-registered')
}
// ══════════ Review 2026-09-27, second round: the fixes' own defects ══════════
{
  // A 2-1 SURVIVOR the audit then demoted has a refuter (the losing lens), so the first
  // fallback still published that lens's objection as `why` and dropped the audit's reason.
  const { out } = await run('R11 2-1 survivor demoted by the audit', { question: 'Q', depth: 'standard' },
    { oneRefuter: true, cite_all_unsupported: true })
  const dem = (out.refuted || []).filter(r => /citation-audit/.test(r.killedBy))
  ok(dem.length > 0 && dem.every(r => r.why === 'the page says nothing of the kind'),
     "a 2-1 survivor demoted by the audit says the AUDIT's reason, not the losing lens's")
}
{
  // The rescue pass has its own cap; what it cut was counted nowhere and the synthesis
  // disclosure blamed the main panel budget.
  const { out, prompts } = await run('R12 rescue-cap cuts are counted', { question: 'Q', depth: 'standard' },
    { wipeSubQuestion: SQ[2], rescueTarget: SQ[2], rescueIndex: 3, rescueMany: true })
  const st = out.stats
  ok(out.rescue && out.rescue.claimsCutByRescueCap > 0 &&
     st.claimsDroppedBeforeVerify + st.claimsExcludedNonCitable + st.claimsVerified === st.claimsExtracted,
     'dropped + excluded + verified == extracted after a capped rescue (' + st.claimsDroppedBeforeVerify + '+' +
     st.claimsExcludedNonCitable + '+' + st.claimsVerified + ' vs ' + st.claimsExtracted + ')')
  const syn = (prompts.find(p => p.label === 'synthesize') || {}).prompt || ''
  ok(/rescue pass's own cap/.test(syn), 'and synthesis is told which cap cut them')
}
{
  // G1: under the default flag policy the flags sat only in processCritique, where a
  // reader of the summary never looks. summaryAnnotated marks each locatable flag in place.
  const sum = 'Wages rose five percent in the treated counties. Employment was flat across every group studied.'
  const { out } = await run('R13 flagged sentences marked in the summary', { question: 'Q', depth: 'standard' },
    { summary: sum, criticVerbatim: ['Employment was flat across every group studied.'] })
  ok(out.summary === sum, 'under the default flag policy the summary itself is untouched')
  ok((out.summaryAnnotated || '').includes('[UNTRACEABLE: Employment was flat across every group studied.]') &&
     out.processCritique.markedInSummary === 1,
     'summaryAnnotated marks the flagged sentence in place, and markedInSummary counts it')
}
{
  // Review of 1.18.0: a duplicate or substring flag nested a second marker inside the
  // first and counted one sentence twice. One locator (flagSpans) now serves both uses.
  const sum = 'Wages rose five percent in the treated counties. Employment was flat across every group studied.'
  const { out } = await run('R14 one flagged sentence is one marker', { question: 'Q', depth: 'standard' },
    { summary: sum, criticVerbatim: ['Employment was flat across every group studied.',
      'was flat across every group studied.', 'Employment was flat across every group studied.'] })
  ok(out.processCritique.markedInSummary === 1 && (out.summaryAnnotated.match(/\[UNTRACEABLE:/g) || []).length === 1,
     'duplicate and substring flags mark the sentence once (' + out.summaryAnnotated + ')')
}
{
  // Map review 2026-09-27: failed stages and early exits say what happened.
  const cf = await run('R15 critic step fails', { question: 'Q', depth: 'standard' }, { criticFails: true })
  ok(cf.out.processCritique.criticsReturned === 0 && cf.out.processCritique.criticNotRun,
     'a failed critic step says the summary was NOT audited (criticsReturned 0)')
  const { out, prompts } = await run('R16 gap analyst fails', { question: 'Q', depth: 'standard' }, { gapFails: true })
  const syn = (prompts.find(p => p.label === 'synthesize') || {}).prompt || ''
  ok(out.honestLimits.coverageNotScored && /Not scored: The gap analyst failed/.test(syn),
     'a failed gap analyst is recorded in honestLimits and told to synthesis')
  const fo = await run('R17 every claim non-citable', { question: 'Q', depth: 'standard' }, { farmOnly: true })
  ok(/non-citable source/.test(fo.out.summary) && !/all empty/.test(fo.out.summary),
     'all claims non-citable is its own reason (' + fo.out.summary.slice(0, 60) + ')')
  const nf = await run('R18 framing-less early exit', { question: 'Q', depth: 'standard' }, { no_framing: true, emptyFetch: true })
  ok(nf.out.honestLimits.noFramingContract, 'an early exit on a framing-less run carries noFramingContract too')
}
console.log('\n════════ FINAL ════════')
console.log(pass + ' passed, ' + fail + ' failed')
process.exit(fail ? 1 : 0)
