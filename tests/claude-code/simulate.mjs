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

function makeAgent(cfg) {
  return async (prompt, opts = {}) => {
    calls++
    const L = opts.label || ''
    seenLabels.push(L)

    if (L === 'framing') {
      if (cfg.no_framing) return null
      // An EMPTY framing contract: type-valid, schema-invalid, and invisible until
      // the report came out with nothing adjudicated. Fires once, then behaves. (#16)
      if (cfg.short_framing_once && !cfg._shortFired) {
        cfg._shortFired = true
        return { decisionAtStake: 'd', keyQuestion: 'k', assumptions: [],
                 whatWouldChangeTheAnswer: [], hypotheses: [] }
      }
      return { decisionAtStake: 'd', keyQuestion: 'k', assumptions: ['a1', 'a2'],
               whatWouldChangeTheAnswer: ['w1', 'w2'],
               hypotheses: [{ hypothesis: 'h1', killCriterion: 'k1' }, { hypothesis: 'h2', killCriterion: 'k2' }] }
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
      const shared = { url: 'https://example.org/shared', title: 'Shared doc', relevance: 'high' }
      if (p === 'P0') return { results: [shared, { url: 'https://a.org/1', title: 'A1', relevance: 'high' }] }
      if (p === 'P1') return { results: [shared, { url: 'https://b.org/2', title: 'B2', relevance: 'medium' }] }
      if (p === 'P2') return { results: [
        { url: 'https://evil.com\\@trusted.org/x', title: 'spoof', relevance: 'high' },
        { url: 'https://аmazon.com/idn', title: 'idn homograph', relevance: 'low' }] }
      if (p.startsWith('rescue')) return { results: [{ url: 'https://primary-' + p + '.org/doc', title: 'primary ' + p, relevance: 'high' }] }
      if (p === 'FU0') return { results: [{ url: 'https://followup.org/deep', title: 'FU', relevance: 'high' }] }
      return { results: [{ url: 'https://' + p.toLowerCase() + '.org/p', title: p, relevance: 'medium' }] }
    }

    if (L.startsWith('fetch:')) {
      if (cfg.emptyFetch) return { sourceQuality: 'unreliable', claims: [] }
      const isRescue = /primary-rescue/.test(prompt)
      if (isRescue) {
        const sq = (prompt.match(/rescue(\d)/) || [0, '1'])[1]
        return { sourceQuality: 'primary', publishDate: '2026-01-01', claims: [
          { claim: 'RESCUED-' + calls + ' primary evidence', quote: 'q', importance: 'central',
            subQuestionIndex: (cfg.rescueIndex || 3), answersSubQuestion: cfg.rescueTarget || SQ[2] }]}
      }
      // Spread claims across sub-questions so coverage balancing has something to balance.
      const a = SQ[calls % SQ.length], b = SQ[(calls + 1) % SQ.length]
      return { sourceQuality: 'primary', publishDate: '2026-01-01', claims: [
        { claim: 'CLAIM-' + calls + ' [' + a + '] concrete', quote: 'quote ' + calls, importance: 'central',
          subQuestionIndex: (calls % SQ.length) + 1, answersSubQuestion: a },
        { claim: 'CLAIM-' + calls + 'b [' + b + '] detail', quote: 'quote b ' + calls, importance: 'supporting',
          subQuestionIndex: ((calls + 1) % SQ.length) + 1, answersSubQuestion: b },
      ]}
    }

    if (L.startsWith('gap-analysis')) return {
      coverage: SQ.map((q, i) => ({ subQuestion: q, status: i === 0 ? 'answered' : i === 2 ? 'unanswered' : 'partial', note: 'n' })),
      contradictions: ['Source A says X, source B says not-X'],
      followUps: cfg.noFollowUps ? [] : [{ label: 'FU0', query: 'followup query', reason: 'closes SQ3' }],
    }

    if (/^(support|counter|provenance):/.test(L)) {
      const lens = L.split(':')[0]
      if (cfg.allVerifiersDie) return null
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
      const n = parseInt((prompt.match(/CLAIM-(\d+)/) || [0, '3'])[1], 10)
      const mode = n % 5
      return { support: mode === 0 ? 'unsupported' : mode === 1 ? 'partial' : mode === 2 ? 'unreachable' : 'supported',
               reasoning: 'blind audit', locatedQuote: 'located' }
    }

    if (L === 'synthesize') {
      if (cfg.noSynth) return null
      return { answerFirst: 'The answer, stated first.', hingeNumber: '86% vs 81%', baseRate: 'none in evidence',
               summary: 'Executive summary.',
               findings: [{ claim: 'Merged 1', confidence: 'high', sources: ['https://a.org/1'], evidence: 'ev',
                            vote: '3-0', citationCheck: 'supported', sourceTier: 'T1', factOrInference: 'fact' }],
               contradictions: ['synth contradiction'],
               hypothesisVerdicts: [
                 { hypothesis: 'h1', verdict: 'killed', killCriterion: 'k1',
                   reasoning: 'claim [0] triggers it', claimsCited: [0] },
                 { hypothesis: 'h2', verdict: 'untested', killCriterion: 'k2',
                   reasoning: 'no confirmed claim bears on it' }],
               strongestArgumentAgainst: 'the crux was never evidenced',
               whatWouldChangeThisCall: ['a real RCT'],
               caveats: 'caveats', openQuestions: ['OQ1'] }
    }

    if (L.startsWith('critic:')) return {
      untraceableStatements: ['stmt 2 untraceable'], coverageGaps: ['no non-English sources'], planFlaws: ['SQ2 leading'],
      verdict: L.endsWith('2') ? 'material-gaps' : 'minor-gaps', rationale: 'because' }

    throw new Error('UNEXPECTED AGENT LABEL: ' + L)
  }
}

export async function run(name, args, cfg = {}) {
  logs.length = 0; seenLabels.length = 0; calls = 0
  const fn = new Function('agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget',
    '"use strict"; return (async () => {' + SRC + '})()')
  const out = await fn(makeAgent(cfg), parallel, pipeline, phase, log, args, { total: null, spent: () => 0, remaining: () => Infinity })
  console.log('\n══════ ' + name + ' ══════')
  return { out, logs: [...logs], labels: [...seenLabels], calls }
}
export { SQ }
