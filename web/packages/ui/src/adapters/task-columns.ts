// The tasks list's columns (`ca-task-table`): a row per task of the run
// (`TaskRow`), its attempts, time, tokens, cost and status.
import { addRow, emptySpend, isPython, runRelative, type JournalRow, type Spend, type TaskOutcome, type TaskRow } from '@contraagent/api';
import type { DataColumn } from '@contraagent/elements/data-table';
import { pill } from '@contraagent/elements/primitives';
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { outcomeMark, outcomeTone } from '../lib/tone.js';
import { executorIcon } from '../words/executor.js';
import { facts, fmtDur, localTime, tokenCount, usd } from '../words/format.js';
import { deferredText, deferredTip, notStartedCause, locksNames, locksShort, passLabel, priorityText, priorityTip, taskStatusLabel, waitCause } from '../words/index.js';

export interface TaskColumnsContext {
  /** The run id: paths in a cause are shown relative to it. */
  run: string;
  /** The run is running: a task that has not started is waiting; in a run that is over, it did not run. */
  live: boolean;
  /** What happened to each task of the run (`deriveRun(...).outcomes`). */
  outcomes: ReadonlyMap<string, TaskOutcome>;
  /** Every task of the run, filtered or not: a kind and unit with more than one task names each one's pass. */
  all: readonly TaskRow[];
  /** The rows shown: the time bars are relative to their longest. */
  rows: readonly TaskRow[];
  /** The run's journal: tokens and cost per task, over all its attempts. */
  journal: readonly JournalRow[];
}

const none = () => msg('none', { id: 'none', desc: 'An empty value' });

/** Why a task that never ran did not run (what stopped it, or the earlier tasks it waits for), or why a task was partly done; '' when unknown. */
function cause(t: TaskRow, ctx: TaskColumnsContext): string {
  if (t.outcome === 'not_started') return notStartedCause(t, ctx.outcomes, ctx.run);
  if (t.outcome === 'partial') return runRelative(t.attempts[t.attempts.length - 1]?.reason ?? '', ctx.run);
  if (t.outcome === 'waiting' && t.deferred) return deferredText(t.deferredCause, t.deferred, t.deferredIn);
  if (t.outcome === 'waiting') return waitCause(t.waits_for.map((k) => ctx.outcomes.get(k) ?? { kind: k }));
  return '';
}

/** The columns of the tasks list. */
export function taskColumns(ctx: TaskColumnsContext): DataColumn<TaskRow>[] {
  // A kind and unit with more than one task (a loop's passes): each row names its pass.
  const per = new Map<string, number>();
  for (const t of ctx.all) per.set(`${t.kind}|${t.unit}`, (per.get(`${t.kind}|${t.unit}`) ?? 0) + 1);
  const maxWall = Math.max(1, ...ctx.rows.map((t) => t.wall_s));
  const spend = new Map<string, Spend>();
  for (const r of ctx.journal) addRow(spend.get(r.key) ?? spend.set(r.key, emptySpend()).get(r.key)!, r);
  // A task that has not run (refused, skipped, waiting) has no attempts and no time.
  const ran = (t: TaskRow) => t.tries.length > 0;
  // Tokens and cost: 'none' for a task that never ran, '—' for one that reported none (a Python task).
  const spent = (t: TaskRow, show: (s: Spend) => unknown) => {
    if (!ran(t)) return html`<span class="jdim">${none()}</span>`;
    const s = spend.get(t.key);
    return s?.reported ? show(s) : html`<span class="jdim">—</span>`;
  };
  return [
    {
      id: 'task',
      header: msg('Task'),
      tip: msg('Kind · unit'),
      width: 'minmax(220px, 0.6fr)',
      rowHeader: true,
      text: (t) => t.key,
      cell: (t) => {
        const py = isPython(t);
        const pass = t.pass !== null && (per.get(`${t.kind}|${t.unit}`) ?? 0) > 1 ? t.pass : null;
        return html`<span class="grow jmono" title=${t.key}>
          ${executorIcon(py, py ? msg('Python task') : msg('Agent task'))}${t.kind}
          ${t.unit ? html`<span class="jdim">· ${t.unit}</span>` : nothing}${pass !== null ? html`<span class="pass">${passLabel(pass)}</span>` : nothing}
          ${t.claims?.length ? html`<span class="jdim also" title=${locksNames(t.claims)}>${locksShort(t.claims)}</span>` : nothing}
          ${t.priority ? html`<span class="jdim also" title=${priorityTip()}>${priorityText(t.priority)}</span>` : nothing}
        </span>`;
      },
    },
    { id: 'attempts', header: msg('Attempts'), tip: msg('Attempts that ran'), align: 'end', width: '64px', cell: (t) => t.tries.length },
    {
      id: 'time',
      header: msg('Time'),
      tip: msg('Sum over all attempts'),
      align: 'end',
      width: '132px',
      cell: (t) =>
        html`<span class="wall">${ran(t)
          ? html`${fmtDur(t.wall_s)}<span class="jdur"><i class=${isPython(t) ? '' : 'llm'}
              style="width:${Math.max(4, Math.round((100 * t.wall_s) / maxWall))}%"></i></span>`
          : html`<span class="jdim">${none()}</span><span class="jdur" style="visibility:hidden"></span>`}</span>`,
    },
    {
      id: 'tokens',
      header: msg('Tokens'),
      tip: msg('Input and output tokens, all attempts'),
      align: 'end',
      width: '72px',
      cell: (t) =>
        spent(t, (s) => {
          const cache = facts(msg(str`Cache read ${tokenCount(s.cache_read)}`), msg(str`Cache write ${tokenCount(s.cache_creation)}`));
          return html`<span title=${cache}>${tokenCount(s.input + s.output)}</span>`;
        }),
    },
    { id: 'cost', header: msg('Cost'), tip: msg('Reported by the coding agent'), align: 'end', width: '72px', cell: (t) => spent(t, (s) => usd(s.cost)) },
    {
      id: 'ended',
      header: msg('Last attempt ended'),
      align: 'end',
      width: '128px',
      cell: (t) => html`<span class="meta">${ran(t) ? localTime(t.tries[t.tries.length - 1]?.ts, true) : none()}</span>`,
    },
    {
      id: 'status',
      header: msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' }),
      width: 'minmax(240px, 1fr)',
      cell: (t) => {
        const why = cause(t, ctx);
        const tip = t.outcome === 'waiting' && t.deferred ? deferredTip(t.deferredCause) || t.deferred : '';
        return html`${pill({ text: taskStatusLabel(t.outcome, ctx.live && !t.deferred), tone: outcomeTone(t.outcome), mark: outcomeMark(t.outcome), title: t.last_stop })}${why
          ? html`<span class="cause" title=${tip || nothing}>${why}</span>`
          : nothing}`;
      },
    },
  ];
}
