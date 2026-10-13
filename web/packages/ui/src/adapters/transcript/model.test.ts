import type { TranscriptEvent } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { applyEvents, emptyTranscript, type ToolItem } from './model.js';
import { checkMessage, checkName, classifyRounds, fixupErrors } from './rounds.js';
import { webResults } from './web.js';
import { launchWho } from './who.js';

const launch = (model: string, role = 'writer'): TranscriptEvent => ({
  type: 'launch',
  argv: ['/usr/bin/claude', '-p', '--model', model],
  cwd: '/w',
  prompt: `TELEMETRY run=r task=k role=${role}\n\nDo it.`,
});

const fold = (events: TranscriptEvent[]) => {
  const t = emptyTranscript();
  const shown = applyEvents(t, events);
  return { t, shown };
};

describe('transcript model', () => {
  it('reads who ran a launch from its argv and TELEMETRY line', () => {
    expect(launchWho({ argv: ['/x/omp', '-m', 'gpt'], prompt: 'TELEMETRY role=-' })).toEqual({ agent: 'omp', model: 'gpt', role: '' });
  });

  it('claude: one round per launch, deltas accumulate into one bubble, tool start and end share a card', () => {
    const { t, shown } = fold([
      launch('m1'),
      { type: 'message_update', ev: 'text_delta', delta: 'Hel' },
      { type: 'message_update', ev: 'text_delta', delta: 'lo' },
      { type: 'tool_execution_start', tool: 'Bash', cmd: 'ls -la\nmore', intent: 'look', call: 'c1' },
      { type: 'tool_execution_end', tool: null, out: 'a b', err: false, call: 'c1' },
      { type: 'message_update', ev: 'text_delta', delta: 'done' },
      launch('m2'),
      { type: 'tool_execution_end', tool: null, out: 'x', err: true, call: 'c9' },
    ]);
    expect(shown).toBe(8);
    expect(t.rounds.map((r) => [r.id, r.who])).toEqual([
      ['r0', { agent: 'Claude Code', model: 'm1', role: 'writer' }],
      ['r1', { agent: 'Claude Code', model: 'm2', role: 'writer' }],
    ]);
    const items = t.rounds[0]!.items;
    expect(items.map((i) => i.type)).toEqual(['message', 'tool', 'message']);
    expect(items[0]).toMatchObject({ text: 'Hello' });
    expect(items[1]).toMatchObject({ name: 'Bash', icon: 'bash', summary: 'ls -la', intent: 'look', body: 'ls -la\nmore', output: 'a b', status: 'ok' });
    // a result with no start opens its own card, in the round it arrived in
    expect(t.rounds[1]!.items[0]).toMatchObject({ name: 'tool', status: 'error', output: 'x' });
  });

  it('omp: duplicate call styles land in one card; a late duplicate only adds the summary; an empty repeat keeps the result', () => {
    const { t } = fold([
      { type: 'acall', tool: 'mcp_read', cmd: '', call: 'c1', intent: '' },
      { type: 'tool_execution_start', tool: 'mcp_read', cmd: 'a.txt', intent: 'read it', call: 'c1' },
      { type: 'tool_execution_end', tool: 'mcp_read', out: 'content', err: false, call: 'c1' },
      { type: 'aresult', tool: 'mcp_read', call: 'c1', out: '', err: false },
      { type: 'tool_execution_update', tool: 'mcp_read', cmd: 'later', intent: 'other', call: 'c1' },
    ]);
    const cards = t.rounds[0]!.items as ToolItem[];
    expect(cards).toHaveLength(1);
    expect(cards[0]).toMatchObject({ id: 'call:c1', icon: 'read', summary: 'a.txt', intent: 'read it', output: 'content', status: 'ok' });
  });

  it('a late duplicate fills a summary the card lacks', () => {
    const { t } = fold([
      { type: 'tool_execution_end', tool: 'grep', out: 'hit', err: false, call: 'c' },
      { type: 'acall', tool: 'grep', cmd: 'needle', call: 'c', intent: '' },
    ]);
    expect(t.rounds[0]!.items[0]).toMatchObject({ summary: 'needle', output: 'hit' });
  });

  it('events before any launch open an implicit round; notices, retries, summaries and echoed prompts', () => {
    const { t, shown } = fold([
      { type: 'notice', text: 'session init:  cwd=/w   model=claude-x tools=3' },
      { type: 'message_start', role: 'user', text: 'the prompt' },
      { type: 'message_start', role: 'assistant', text: 'ignored' },
      { type: 'turn_end', thinking: 'summary' },
      { type: 'turn_end' },
      { type: 'auto_retry_start', attempt: 2, err: '429' },
      { type: 'agent_start' },
      { type: 'message_update', ev: 'text_delta', delta: '' },
    ]);
    expect(shown).toBe(4);
    const r = t.rounds[0]!;
    expect(r.launch).toBeNull();
    expect(r.who).toEqual({ agent: '', model: 'claude-x', role: '' });
    expect(r.items).toMatchObject([
      { type: 'notice', text: 'session init: cwd=/w model=claude-x tools=3' },
      { type: 'prompt', text: 'the prompt' },
      { type: 'reasoning', text: 'summary' },
      { type: 'event', icon: '↻', text: '429' },
    ]);
  });

  it('a session-init notice does not replace a model the argv named', () => {
    const { t } = fold([launch('m1'), { type: 'notice', text: 'session init: model=other' }]);
    expect(t.rounds[0]!.who?.model).toBe('m1');
  });

  it('item ids are stable when the same events are folded again', () => {
    const events: TranscriptEvent[] = [launch('m'), { type: 'notice', text: 'n' }, { type: 'tool_execution_start', tool: 'x', cmd: '', intent: '', call: '' }];
    expect(fold(events).t.rounds[0]!.items.map((i) => i.id)).toEqual(fold(events).t.rounds[0]!.items.map((i) => i.id));
  });
});

describe('rounds as tries and fix-ups', () => {
  const first = { prompt: 'TELEMETRY run=r key=k role=x\n\nTask call' };
  const fix = {
    prompt:
      'The output file(s) you wrote do not pass their checks. Fix them.\n\n## /w/out/a.json\nErrors:\n- /w/out/a.json: [three_points] points: exactly three expected, got 2\nRequired JSON Schema:\n```json\n{}\n```',
  };

  it('a fix-up continues its try; a fresh session is a new try', () => {
    const rounds = classifyRounds([first, fix, first], [
      { attempt: 0, ok: false, stop: 'error', reason: 'tool crashed' },
      { attempt: 1, ok: true, stop: 'completed' },
    ]);
    expect(rounds.map((r) => [r.kind, r.tryNo, r.fixupNo, r.result])).toEqual([
      ['try', 1, 0, 'rejected'],
      ['fixup', 1, 1, 'failed'],
      ['try', 2, 0, 'ok'],
    ]);
    expect(rounds[0]?.rejectedWith).toEqual(['/w/out/a.json: [three_points] points: exactly three expected, got 2']);
    expect(checkName(rounds[0]!.rejectedWith[0]!)).toBe('three_points');
    expect(rounds[1]?.row?.reason).toBe('tool crashed');
  });

  it('a resumed run numbers attempts from 0 again: each try takes the row in its place', () => {
    const rounds = classifyRounds([first, first], [
      { attempt: 0, ok: true, stop: 'completed', reason: 'first start' },
      { attempt: 0, ok: true, stop: 'completed', reason: 'resumed' },
    ]);
    expect(rounds.map((r) => [r.tryNo, r.result, r.row?.reason])).toEqual([
      [1, 'ok', 'first start'],
      [2, 'ok', 'resumed'],
    ]);
  });

  it('a fresh session within a try that has more hops is a model switch, not a new try', () => {
    const rounds = classifyRounds([first, first], [
      {
        attempt: 0,
        ok: true,
        stop: 'completed',
        hops: [
          { model: 'primary-model', stop: 'rate_limited' },
          { model: 'fallback-model', stop: 'completed' },
        ],
      },
    ]);
    expect(rounds.map((r) => [r.kind, r.tryNo, r.hopNo, r.model, r.result, r.switchedStop])).toEqual([
      ['try', 1, 0, 'primary-model', 'switched', 'rate_limited'],
      ['switch', 1, 1, 'fallback-model', 'ok', ''],
    ]);
  });

  it('a check error reads as check: message', () => {
    expect(checkMessage('/w/out/a.json: [three_points] points: exactly three expected, got 2')).toBe(
      'three_points: points: exactly three expected, got 2',
    );
    expect(checkMessage('plain')).toBe('plain');
  });

  it('a round whose try has no journal row yet has no result', () => {
    expect(classifyRounds([first], []).map((r) => r.result)).toEqual([null]);
    expect(fixupErrors('no errors here')).toEqual([]);
  });
});

describe('web search', () => {
  it('a web search card keeps its query; another tool has none', () => {
    const { t } = fold([
      launch('m1'),
      { type: 'tool_execution_start', tool: 'web_search', cmd: 'omp rpc', web_query: 'omp rpc', intent: '', call: 'w1' },
      { type: 'tool_execution_end', tool: 'web_search', out: '[1] omp\n    https://omp.sh/', err: false, call: 'w1' },
      { type: 'tool_execution_start', tool: 'bash', cmd: 'ls', intent: '', call: 'b1' },
    ]);
    const [search, bash] = t.rounds[0]?.items as ToolItem[];
    expect(search?.query).toBe('omp rpc');
    expect(search?.links).toEqual([{ title: 'omp', url: 'https://omp.sh/' }]);
    expect(bash?.query).toBeUndefined();
  });

  it("reads Claude Code's links, omp's numbered results, else bare URLs", () => {
    const claude = 'Web search results for query: "x"\n\nLinks: [{"title":"A \\"quoted\\" page","url":"https://a.example/1"},{"title":"B","url":"https://b.example/"}]';
    expect(webResults(claude)).toEqual([
      { title: 'A "quoted" page', url: 'https://a.example/1' },
      { title: 'B', url: 'https://b.example/' },
    ]);
    const omp = '[1] oh my pi\n    https://ohmypi.xyz/\n    oh my pi\n[2] npm\n    https://www.npmjs.com/package/x\n';
    expect(webResults(omp)).toEqual([
      { title: 'oh my pi', url: 'https://ohmypi.xyz/' },
      { title: 'npm', url: 'https://www.npmjs.com/package/x' },
    ]);
    expect(webResults('see https://c.example/a and https://c.example/a, javascript:alert(1)')).toEqual([
      { title: 'https://c.example/a', url: 'https://c.example/a' },
    ]);
    expect(webResults(null)).toEqual([]);
  });

  it("reads a real Claude Code WebSearch result (claude-haiku-5-5, 2026-10)", () => {
    const real =
      'Web search results for query: "oh-my-pi coding agent"\n\nLinks: [{"title":"oh-my-pi (omp) is a coding agent CLI built on Pi with batteries included","url":"https://ports.macports.org/port/oh-my-pi/"},{"title":"<p align=\\"center\\">","url":"https://cdn.jsdelivr.net/gh/can1357/oh-my-pi@main/README.md"},{"title":"Oh My Pi: The Agent Everyone\'s Talking About, and the Minimal Pi Underneath","url":"https://yuv.ai/blog/oh-my-pi-omp-explained"}]\n\nOh My Pi (omp) is an open-source terminal coding agent. See https://omp.sh/ for more.';
    expect(webResults(real)).toEqual([
      { title: 'oh-my-pi (omp) is a coding agent CLI built on Pi with batteries included', url: 'https://ports.macports.org/port/oh-my-pi/' },
      { title: '<p align="center">', url: 'https://cdn.jsdelivr.net/gh/can1357/oh-my-pi@main/README.md' },
      { title: "Oh My Pi: The Agent Everyone's Talking About, and the Minimal Pi Underneath", url: 'https://yuv.ai/blog/oh-my-pi-omp-explained' },
    ]);
  });

  it('a web page read keeps its URL', () => {
    const { t } = fold([
      launch('m1'),
      { type: 'tool_execution_start', tool: 'WebFetch', cmd: 'https://omp.sh/', web_fetch: 'https://omp.sh/', intent: 'what is it', call: 'f1' },
    ]);
    const [fetch] = t.rounds[0]?.items as ToolItem[];
    expect([fetch?.page, fetch?.query, fetch?.intent]).toEqual(['https://omp.sh/', undefined, 'what is it']);
  });
});
