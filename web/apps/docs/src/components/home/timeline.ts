// What the landing page's replay plays, made when the site is built: the demo
// pipeline's showcase run (src/fixtures/demo-run.json and the transcripts of
// public/demo/data/, written by scripts/fixture.py), the lines of its flow code
// quoted from the tested example, and the moments of the run, each from its data.
import type { JournalRow, Plan, TranscriptEvent } from '@contraagent/api';
import fixture from '../../fixtures/demo-run.json';
import { repoFile } from '../../lib/repo';
import { highlight } from './python';

export const TASKS = 'src/contraagent/docs/examples/demo/tasks.py';
const STREAMS = 'web/apps/docs/public/demo/data/runs/docs/streams';

/** A quoted line of code: its line number in the file and its HTML ('' for a gap between quotes). */
export interface CodeLine { n: number; html: string }

/** A task whose transcript the replay shows while it runs, and when its correction round started (`corrected`). */
export interface Spot { key: string; name: string; from: number; to: number; corrected: number; events: TranscriptEvent[]; times: number[]; rows: JournalRow[] }

/**
 * A moment of the run, at a time of the run (seconds from its start), and the panel
 * of the replay that shows it: a correction in the transcript (of the task `spot`, a
 * Spot's key), the rest in the graph.
 */
export interface Moment { at: number; text: string; shows: 'graph' | 'transcript'; spot?: string }

export interface Timeline {
  run: string;
  /** The run's first and last time (epoch seconds). */
  t0: number;
  t1: number;
  plan: Plan;
  journal: JournalRow[];
  spots: Spot[];
  moments: Moment[];
}

const epoch = (ts = ''): number => Date.parse(ts) / 1000;
const name = (r: { kind: string; unit?: string }): string => (r.unit ? `${r.kind} · ${r.unit}` : r.kind);

/**
 * The lines of tasks.py from the first line holding `from` to the line holding `to`
 * (inclusive), each with its number; the replay lights the line a running task was created on.
 */
function lines(file: string[], from: string, to: string): CodeLine[] {
  const start = file.findIndex((l) => l.includes(from));
  const end = file.findIndex((l, i) => i >= start && l.includes(to));
  if (start < 0 || end < 0) throw new Error(`${TASKS}: no lines from ${JSON.stringify(from)} to ${JSON.stringify(to)}`);
  return file.slice(start, end + 1).map((l, i) => ({ n: start + i + 1, html: l }));
}

/** The code the replay types: the summarize task's definition and the flow, without the docstrings. */
export function code(): CodeLine[] {
  const file = repoFile(TASKS).split('\n');
  const parts = [
    lines(file, 'summarize = agent_task(', ')'),
    lines(file, 'def review_loop(', 'def review_loop('),
    lines(file, '    try:', 'return summary'),
    lines(file, 'def docs(', 'def docs('),
    lines(file, 'summaries = yield [review_loop', 'return (yield report('),
  ];
  const out: CodeLine[] = [];
  for (const p of parts) {
    const last = out.at(-1);
    if (last && p[0].n > last.n + 1) out.push({ n: 0, html: '' });
    out.push(...p);
  }
  const html = highlight(out.map((l) => l.html));
  return out.map((l, i) => ({ n: l.n, html: html[i] }));
}

/** The transcript of a task beside the export, each event at a time: a launch at its own, the others spread up to the next. */
function spot(journal: JournalRow[], key: string): Spot {
  const rows = journal.filter((r) => r.key === key);
  const row = rows.at(-1);
  if (!row) throw new Error(`the demo run has no task ${key}`);
  const events = (JSON.parse(repoFile(`${STREAMS}/${key}.json`)) as { events: TranscriptEvent[] }).events;
  const to = epoch(row.ts);
  const launches = events.flatMap((e, i) => (e.type === 'launch' && typeof e['ts'] === 'number' ? [{ i, ts: e['ts'] }] : []));
  const times = events.map((_, i) => {
    const k = launches.findLastIndex((l) => l.i <= i);
    const here = launches[k];
    const next = launches[k + 1];
    const end = next ? next.ts - 0.15 : to;
    const span = (next ? next.i : events.length) - here.i;
    return here.ts + ((end - here.ts) * (i - here.i)) / Math.max(1, span);
  });
  const second = events.findIndex((e, i) => i > 0 && e.type === 'launch');
  return { key, name: name(row), from: times[0], to, corrected: second < 0 ? to : times[second], events, times, rows };
}

/** The check a round error names ("<path>: [check] message"). */
const check = (e: string): string => /: \[([^\]]+)\] /.exec(e)?.[1] ?? 'a validator';

export function timeline(): Timeline {
  const plan = fixture.plan as unknown as Plan;
  const journal = fixture.journal as unknown as JournalRow[];
  const t0 = Math.min(...plan.nodes.map((n) => epoch(n.ts)));
  const t1 = Math.max(...journal.map((r) => epoch(r.ts)));

  // The tasks corrected in their own session: their transcripts, and the round after the failed checks.
  const corrected = journal.filter((r) => (r.rounds ?? 1) > 1);
  const spots = corrected.map((r) => spot(journal, r.key));
  const moments: Moment[] = [];
  for (const s of spots) {
    const row = s.rows.at(-1)!;
    const checks = (row.round_errors?.[0] ?? []).map(check);
    const failed = checks.length === 1 ? `failed the check ${checks[0]}` : `failed the checks ${checks.slice(0, -1).join(', ')} and ${checks.at(-1)}`;
    moments.push({ at: s.corrected - t0, text: `${s.name} ${failed}. The same agent session corrected it.`, shows: 'transcript', spot: s.key });
  }
  // A model switch: the first hop's stop, then the hop that finished.
  for (const r of journal.filter((r) => (r.hops ?? []).length > 1)) {
    const hops = r.hops ?? [];
    const [first, last] = [hops[0], hops.at(-1)!];
    moments.push({
      at: epoch(r.ts) - (r.wall_s ?? 0) + (first.wall_s ?? 0) - t0,
      text: `${name(r)} ${first.stop === 'rate_limited' ? 'was rate limited' : `stopped (${first.stop})`} on ${first.model}. A model switch ran it on ${last.model}.`,
      shows: 'graph',
    });
  }
  // A loop's second pass: the first task created in it.
  const second = plan.nodes.filter((n) => (n.flow ?? []).some((f) => (f.loops ?? []).some((l) => (l.pass ?? 1) > 1)));
  const units = [...new Set(second.map((n) => n.unit ?? ''))];
  if (second.length) {
    const first = second.reduce((a, b) => (epoch(a.ts) <= epoch(b.ts) ? a : b));
    const revise = plan.nodes.find((n) => n.kind === 'revise' && n.unit === first.unit);
    moments.push({
      at: epoch(revise?.ts ?? first.ts) - t0,
      text: `The review of ${units.join(', ')} did not approve its summary. The loop ran a second pass for ${units.join(', ')}.`,
      shows: 'graph',
    });
  }
  const done = plan.nodes.filter((n) => n.state === 'done').length;
  const tally = fixture.outputs.tally as Record<string, number>;
  const outputs = Object.values(tally).reduce((a, b) => a + b, 0);
  moments.push({
    at: t1 - t0,
    text: `${done} of ${plan.nodes.length} tasks done. ${tally['valid']} of ${outputs} outputs passed their checks.`,
    shows: 'graph',
  });
  moments.sort((a, b) => a.at - b.at);

  // The flow lines the plan names are the lines of tasks.py this page quotes.
  const file = repoFile(TASKS).split('\n');
  for (const n of plan.nodes) {
    const line = n.flow?.at(-1)?.line ?? 0;
    if (!file[line - 1]?.includes(n.kind)) throw new Error(`demo-run.json: ${n.key} names ${TASKS}:${line}, which does not create a ${n.kind} task; run scripts/fixture.py`);
  }
  return { run: fixture.run, t0, t1, plan, journal, spots, moments };
}
