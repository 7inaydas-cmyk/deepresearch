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
  ok(caps.standard === 30 && caps.exhaustive === 50 && caps.quick === 14,
     'verify budgets raised: quick=' + caps.quick + ' standard=' + caps.standard + ' exhaustive=' + caps.exhaustive)
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
  ok(out.processCritique.policy === 'flag' && Array.isArray(out.processCritique.struckFromSummary),
     'strike/flag policy is present and defaults to flag (#4)')
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
                whatWouldChangeTheAnswer: ['an RCT showing harm', 'no effect'], decisionAtStake: 'buy 40 desks' }
  const { out, logs } = await run('T20 contract intake: supplied fields win, the model drafts the rest',
    { question: 'Q', depth: 'standard', contract: sup })
  ok(out.scopeContract && out.scopeContract.keyQuestion === sup.keyQuestion, 'a supplied field reaches the report verbatim')
  ok(out.scopeContract.provenance && out.scopeContract.provenance.assumptions === 'supplied' && out.scopeContract.provenance.hypotheses === 'drafted',
     'provenance is per field: ' + JSON.stringify(out.scopeContract.provenance))
  ok(logs.some(l => /Contract: 4 field\(s\) supplied/.test(l)), 'the log names what was supplied')
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
                decisionAtStake: 'd', hypotheses: [{ hypothesis: 'h1', killCriterion: 'k1' }, { hypothesis: 'h2', killCriterion: 'k2' }] }
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
  ok(/evidenceBase: evidenceBase\(\)/.test(src) && /MIN_CITABLE_SOURCES = 5/.test(src),
     'every exit reports how many citable sources the report rests on')
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
  ok(/preRegistered: !!normHyp/.test(src) && /POST_HOC/.test(src),
     'every hypothesisVerdict is stamped with whether its hypothesis was registered before the search')
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
  ok(/webTextPattern\(frag\)\.exec\(text\)/.test(src) && !/text\.includes\(frag\)/.test(src),
     'the strike matches through webText, not with a plain includes() that misses on any summary containing a quotation mark')
  ok((src.match(/const toRefuted =/g) || []).length === 1,
     'exactly one toRefuted builder - the Python twin had TWO, and fixing one left the happy path on the old shape')
  ok(!/citableSources < MIN_CITABLE_SOURCES\) return/.test(src) && /NOT aborted for being thin/.test(src),
     'a thin run is labelled, never aborted: the thinnest run on record was thin because of a bug, and aborting would have hidden it')
}
console.log('\n════════ FINAL ════════')
console.log(pass + ' passed, ' + fail + ' failed')
process.exit(fail ? 1 : 0)
