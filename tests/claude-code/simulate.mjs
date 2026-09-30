import fs from 'node:fs'
const SRC = fs.readFileSync(new URL('../../integrations/claude-code/deepresearch.js', import.meta.url).pathname, 'utf8')
  .replace(/^export const meta/m, 'const meta')

const logs = []
const log = m => logs.push(m)
const phase = () => {}
const parallel = async thunks => Promise.all(thunks.map(t => Promise.resolve().then(t).catch(() => null)))
const pipeline = async (items, ...stages) => Promise.all(items.map(async (item, idx) => {
  let cur = item
  try { for (const s of stages) cur = await s(cur, item, idx) } catch { return null }
  return cur
}))

const SQ = ['SQ1 premise check', 'SQ2 mechanism', 'SQ3 cost', 'SQ4 counter-case']
let calls = 0
const seenLabels = []
const seenPrompts = []

function makeAgent(cfg) {
  return async (prompt, opts = {}) => {
    calls++
    const L = opts.label || ''
    seenLabels.push(L)
    seenPrompts.push({ label: L, prompt })
    // The runtime THROWS once a token budget is spent; this reproduces it at one label.
    if (cfg.throwAt && L === cfg.throwAt) throw new Error('token budget exhausted')

    if (L === 'framing') {
      if (cfg.no_framing) return null
      // An EMPTY framing contract: type-valid, schema-invalid, and invisible until
      // the report came out with nothing adjudicated. Fires once, then behaves. (#16)
      if (cfg.short_framing_once && !cfg._shortFired) {
        cfg._shortFired = true
        return { decisionAtStake: 'd', keyQuestion: 'k', assumptions: [],
                 whatWouldChangeTheAnswer: [], hypotheses: [] }
      }
      // Hypotheses with enough content words to actually score, so the number a verdict
      // declares can be checked against the one it names.
      if (cfg.misnumbered_verdict || cfg.curly_negation) {
        return { decisionAtStake: 'd', keyQuestion: 'k', assumptions: ['a1', 'a2'],
                 whatWouldChangeTheAnswer: ['w1', 'w2'], needsGeneralWeb: true,
                 hypotheses: [
                   { hypothesis: 'Minimum wage increases reduce teen employment modestly in the first two years', killCriterion: 'k1' },
                   { hypothesis: 'The apparent effect is largely a publication-selection artifact in the older literature', killCriterion: 'k2' }] }
      }
      return { decisionAtStake: 'd', keyQuestion: 'k', assumptions: ['a1', 'a2'],
               whatWouldChangeTheAnswer: ['w1', 'w2'],
               hypotheses: [{ hypothesis: 'h1', killCriterion: 'k1' }, { hypothesis: 'h2', killCriterion: 'k2' }],
               needsGeneralWeb: true }
    }
    if (L.startsWith('plan')) {
      if (cfg.unknown_sentinel_once && !cfg._fired) {
        cfg._fired = true
        return { strategy: 's', subQuestions: '\n<UNKNOWN>\n', perspectives: '\n<UNKNOWN>\n' }
      }
      if (cfg.bad_scope) return { strategy: 'x', subQuestions: [], perspectives: ['a bare string'] }
      if (cfg.plan_string_subq) {
        return { strategy: 's', subQuestions: 'one long prose string of sub-questions',
                 perspectives: Array.from({ length: 6 }, (_, i) => ({ label: 'P' + i, lens: 'l', query: 'q' + i })) }
      }
      return { strategy: 'test strategy', subQuestions: [...SQ],
               perspectives: Array.from({ length: 6 }, (_, i) => ({ label: 'P' + i, lens: 'lens ' + i, query: 'q' + i, rationale: 'r' + i })) }
    }

    if (L.startsWith('search:')) {
      const p = L.slice(7)
      if (cfg.farmOnly) return { results: [{ url: 'https://www.buzzfeed.com/' + p, title: 'farm ' + p, relevance: 'high' }] }
      const shared = { url: 'https://example.org/shared', title: 'Shared doc', relevance: 'high' }
      if (p === 'P0') return { results: [shared, { url: 'https://a.org/1', title: 'A1', relevance: 'high' }] }
      if (p === 'P1') return { results: [shared, { url: 'https://b.org/2', title: 'B2', relevance: 'medium' }] }
      if (p === 'P2') return { results: [
        { url: 'https://evil.com\\@trusted.org/x', title: 'spoof', relevance: 'high' },
        { url: 'https://аmazon.com/idn', title: 'idn homograph', relevance: 'low' }] }
      if (p.startsWith('rescue')) return { results: [
        ...(cfg.farmRescue ? [{ url: 'https://www.buzzfeed.com/' + p, title: 'farm ' + p, relevance: 'high' }] : []),
        { url: 'https://primary-' + p + '.org/doc', title: 'primary ' + p, relevance: 'high' }] }
      if (p === 'FU0') return { results: [{ url: 'https://followup.org/deep', title: 'FU', relevance: 'high' }] }
      return { results: [{ url: 'https://' + p.toLowerCase() + '.org/p', title: p, relevance: 'medium' }] }
    }

    if (L.startsWith('fetch:')) {
      if (cfg.emptyFetch) return { sourceQuality: 'unreliable', claims: [] }
      const isRescue = /primary-rescue/.test(prompt)
      if (isRescue) {
        const sq = (prompt.match(/rescue(\d)/) || [0, '1'])[1]
        // rescueMany: more rescue claims than the rescue pass's own cap holds.
        return { sourceQuality: 'primary', publishDate: '2026-01-01', claims: Array.from(
          { length: cfg.rescueMany ? 20 : 1 }, (_, i) => (
          { claim: 'RESCUED-' + calls + '-' + i + ' primary evidence', quote: 'q', importance: 'central',
            subQuestionIndex: (cfg.rescueIndex || 3), answersSubQuestion: cfg.rescueTarget || SQ[2] })) }
      }
      // Spread claims across sub-questions so coverage balancing has something to balance.
      const a = SQ[calls % SQ.length], b = SQ[(calls + 1) % SQ.length]
      return { sourceQuality: 'primary', publishDate: '2026-01-01', claims: [
        { claim: 'CLAIM-' + calls + ' [' + a + '] concrete', quote: 'quote ' + calls, importance: 'central',
          subQuestionIndex: (calls % SQ.length) + 1, answersSubQuestion: a },
        // longClaim: an oversized, tab-and-newline claim so the report-side caps
        // have a real fixture (2026-09-30) - the per-claim sample rows once shipped raw.
        { claim: cfg.longClaim
            ? 'CLAIM-' + calls + 'b [' + b + '] detail ' + 'word '.repeat(140) + '\n'
            : 'CLAIM-' + calls + 'b [' + b + '] detail',
          quote: 'quote b ' + calls, importance: 'supporting',
          subQuestionIndex: ((calls + 1) % SQ.length) + 1, answersSubQuestion: b },
      ]}
    }

    if (L.startsWith('gap-analysis') && cfg.gapFails) return null
    if (L.startsWith('gap-analysis:r') && !L.startsWith('gap-analysis:r1') && cfg.gapR2Fails) return null
    if (L.startsWith('gap-analysis')) return {
      coverage: SQ.map((q, i) => ({ subQuestion: q, status: i === 0 ? 'answered' : i === 2 ? 'unanswered' : 'partial', note: 'n' })),
      contradictions: ['Source A says X, source B says not-X'],
      followUps: cfg.noFollowUps ? [] : [{ label: 'FU0', query: 'followup query', reason: 'closes SQ3' }],
    }

    if (/^(support|counter|provenance):/.test(L)) {
      const lens = L.split(':')[0]
      if (cfg.allVerifiersDie) return null
      // Every claim survives 2-1: the support lens refutes, the other two pass.
      if (cfg.oneRefuter) return { refuted: lens === 'support', evidence: "the losing lens's objection", confidence: 'high' }
      if (/RESCUED-/.test(prompt)) return { refuted: false, evidence: 'rescued primary source holds', confidence: 'high' }
      // cfg.wipeSubQuestion: kill EVERY claim tagged with that sub-question.
      if (cfg.wipeSubQuestion && prompt.includes('[' + cfg.wipeSubQuestion + ']')) {
        return { refuted: lens !== 'provenance', evidence: 'wiped', confidence: 'high', counterSource: 'https://c.org' }
      }
      const n = parseInt((prompt.match(/CLAIM-(\d+)/) || [0, '0'])[1], 10)
      const doomed = n % 4 === 0
      return { refuted: doomed && lens !== 'provenance', evidence: lens + ' ev', confidence: 'high', counterSource: '' }
    }

    if (L.startsWith('cite:')) {
      if (cfg.cite_all_unsupported) return { support: 'unsupported', reasoning: 'the page says nothing of the kind', locatedQuote: '' }
      if (cfg.cite_echo_keys) return { support: 'unsupported', reasoning: 'no', locatedQuote: '', claim: 'echoed', url: 'https://echoed.example/' }
      const n = parseInt((prompt.match(/CLAIM-(\d+)/) || [0, '3'])[1], 10)
      const mode = n % 5
      // A NUMBER where a string is declared. `required` only ever meant key-present, so
      // this passed the schema exactly as a real quote did and landed in citationAccuracy
      // — the locatedQuote fix was hollow here for as long as the leaf went unchecked.
      const quote = cfg.string_leaf_violation ? 404 : 'located'
      return { support: mode === 0 ? 'unsupported' : mode === 1 ? 'partial' : mode === 2 ? 'unreachable' : 'supported',
               reasoning: 'blind audit', locatedQuote: quote }
    }

    // Restate-or-drop (ported 2026-09-27). `restate_fails` makes the re-audit come back
    // partial again, so the demotion half of the rule is exercised too.
    if (L.startsWith('restate:')) {
      const n = (prompt.match(/CLAIM-(\d+b?)/) || [0, '0'])[1]
      return { claim: 'CLAIM-' + n + ' WEAKENED to what the page carries' }
    }
    if (L.startsWith('cite2:')) {
      return cfg.restate_fails
        ? { support: 'partial', reasoning: 'still overstated', locatedQuote: 'located' }
        : { support: 'supported', reasoning: 'the weakened form is on the page', locatedQuote: 'the weakened quote' }
    }

    if (L === 'synthesize') {
      if (cfg.noSynth) return null
      return { answerFirst: 'The answer, stated first.', hingeNumber: '86% vs 81%', baseRate: 'none in evidence',
               summary: cfg.summary || 'Executive summary.',
               findings: [{ claim: 'Merged 1', confidence: 'high', sources: ['https://a.org/1'], evidence: 'ev',
                            vote: '3-0', citationCheck: 'supported', sourceTier: 'T1', factOrInference: 'fact' }],
               contradictions: ['synth contradiction'],
               // A verdict adjudicating a hypothesis the run NEVER registered, declaring
               // H1 anyway. Stamping believed the number with nothing examined, so this
               // came back `preRegistered: true` — gamed by typing a digit.
               // The opposite of H1, negated with a CURLY apostrophe (review 2026-09-27).
               hypothesisVerdicts: cfg.curly_negation ? [
                 { hypothesis: 'Minimum wage increases don\u2019t reduce teen employment modestly in the first two years',
                   hypothesisNumber: 1, verdict: 'surviving', killCriterion: 'k1', reasoning: 'r' }] :
               cfg.misnumbered_verdict ? [
                 { hypothesis: 'The minimum wage increase caused a decade-long employment decline across all age groups',
                   hypothesisNumber: 1, verdict: 'surviving', killCriterion: 'k1', reasoning: 'r' },
                 { hypothesis: 'H2: The apparent effect is largely a publication-selection artifact in the older literature',
                   hypothesisNumber: 2, verdict: 'killed', killCriterion: 'k2', reasoning: 'r', claimsCited: [0] }] : [
                 { hypothesis: 'h1', hypothesisNumber: 1, verdict: 'killed', killCriterion: 'k1',
                   reasoning: 'claim [0] triggers it', claimsCited: [0] },
                 { hypothesis: 'h2', hypothesisNumber: 2, verdict: 'untested', killCriterion: 'k2',
                   reasoning: 'no confirmed claim bears on it' }],
               // The shape a real Python run produced: a cross-reference to the field
               // itself. `pointer_steelman` reproduces it; `pointer_steelman_hard` makes
               // the re-ask fail too, so the disclosure path is exercised.
               strongestArgumentAgainst: (cfg.pointer_steelman || cfg.pointer_steelman_hard)
                 ? 'See strongestArgumentAgainst field above (duplicate not needed).'
                 : 'the crux was never evidenced',
               whatWouldChangeThisCall: ['a real RCT'],
               caveats: 'caveats', openQuestions: ['OQ1'] }
    }

    if (L === 'steelman-retry') {
      if (cfg.pointer_steelman_hard) return { strongestArgumentAgainst: 'See above.' }
      return { strongestArgumentAgainst:
        'The two crossover trials that carry this conclusion recruited from one university, and ' +
        'selection into them plausibly tracks the outcome measured, so the pooled estimate may be ' +
        'one population counted twice.' }
    }
    if (L.startsWith('critic:') && cfg.criticFails) return null
    if (L.startsWith('critic:')) return {
      untraceableStatements: ['stmt 2 untraceable'], coverageGaps: ['no non-English sources'], planFlaws: ['SQ2 leading'],
      untraceableVerbatim: cfg.criticVerbatim || [],
      verdict: L.endsWith('2') ? 'material-gaps' : 'minor-gaps', rationale: 'because' }

    throw new Error('UNEXPECTED AGENT LABEL: ' + L)
  }
}

export async function run(name, args, cfg = {}) {
  logs.length = 0; seenLabels.length = 0; seenPrompts.length = 0; calls = 0
  const fn = new Function('agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget',
    '"use strict"; return (async () => {' + SRC + '})()')
  const out = await fn(makeAgent(cfg), parallel, pipeline, phase, log, args, { total: null, spent: () => 0, remaining: () => Infinity })
  console.log('\n══════ ' + name + ' ══════')
  return { out, logs: [...logs], labels: [...seenLabels], prompts: [...seenPrompts], calls }
}
export { SQ }
