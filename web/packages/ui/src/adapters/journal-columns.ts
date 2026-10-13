// The history's columns (`ca-journal-table`): a row per finished attempt
// (`JournalRow`), when it ended, the task, its stop, the agent and model, tokens,
// cost, time and the reason.
import { isBad, isLaunched, isPython, runRelative, type JournalRow, type TaskOutcome } from '@contraagent/api';
import type { DataColumn } from '@contraagent/elements/data-table';
import { statusWord } from '@contraagent/elements/primitives';
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { stopTone } from '../lib/tone.js';
import { executorIcon } from '../words/executor.js';
import { facts, fmtDur, kindUnit, localTime, sentence, tokenCount, unreadEvents, usd } from '../words/format.js';
import { attemptLabel, correctionsText, credentialLabel, credentialTip, modelSwitch, notStartedCause, outcomeLabel, stopLabel } from '../words/index.js';
import { accountReading, readingShort } from '../words/quota.js';
import { attemptFacts } from './filters.js';

export interface JournalColumnsContext {
  /** The run id: paths inside the run directory are shown relative to it. */
  run: string;
  /** What happened to each task (`deriveRun`): a refused row names its cause in words. */
  outcomes: ReadonlyMap<string, TaskOutcome>;
  /** Every row of the journal, in order: the attempts of a task, and the one that later did it. */
  journal: readonly JournalRow[];
  /** The rows shown: the time bars are relative to their longest. */
  rows: readonly JournalRow[];
}

/** A stop as a short column label: a task that never ran is just "not started"; the cause goes to the reason. */
export function shortStop(stop: string | null | undefined): string {
  return stop === 'invalid_input' ? outcomeLabel('not_started') : stopLabel(stop);
}

/** The identity the attempt authenticated as; both when a model switch changed it. */
function identity(e: JournalRow) {
  const ids = [...new Set([...(e.hops ?? []).map((h) => h.credential), e.credential].filter(Boolean))];
  if (!ids.length) return nothing;
  // The subscription usage the attempt's first session started at, when the agent reported one.
  const start = (e.quota ?? [])[0];
  const tip = start ? msg(str`Usage at session start (account-wide): ${accountReading(start)}`) : '';
  // The reading belongs to one account: name it when the row has more than one, or a different one.
  const own = start && ids.length === 1 && (start.credential ?? '') === ids[0];
  const shown = start ? (own ? readingShort(start) : accountReading(start)) : '';
  const tips = [tip, ...ids.map(credentialTip)].filter(Boolean).join('\n');
  return html`<span class="sub" title=${tips || nothing}>${ids.map((c) => credentialLabel(c)).join(' → ')}${start ? html` <span class="q">${shown}</span>` : nothing}</span>`;
}

/** The columns of the history. */
export function journalColumns(ctx: JournalColumnsContext): DataColumn<JournalRow>[] {
  const maxWall = Math.max(1, ...ctx.rows.map((e) => e.wall_s || 0));
  const tries = attemptFacts(ctx.journal);
  const index = new Map(ctx.journal.map((r, i) => [r, i]));
  /** The attempt that later did the task, after this one failed (0: none). */
  const laterTry = (e: JournalRow): number => {
    const f = tries.get(e.key);
    return !e.ok && isLaunched(e) && (f?.lastOk ?? -1) > (index.get(e) ?? 0) ? (f?.lastOkTry ?? 0) : 0;
  };

  /**
   * What the reason column says: the model switch, then (for a row that failed
   * or never ran) the reason, run-relative, then the attempt that later did the task.
   */
  const reason = (e: JournalRow) => {
    const ran = isLaunched(e);
    const sw = modelSwitch(e.hops);
    const run = ctx.run || e.run_id || '';
    const own = ctx.outcomes.get(e.key);
    const cause = e.stop === 'invalid_input' && own ? notStartedCause({ attempts: [e], cause: null }, ctx.outcomes, run) : '';
    const why = cause ? sentence(cause) : (!e.ok || !ran) && e.reason ? runRelative(e.reason, run) : '';
    const n = laterTry(e);
    const later = n ? msg(str`The task was done on attempt ${n}`) : '';
    if (!sw && !why && !later) return html`<span class="jdim">—</span>`;
    return html`${sw ? html`<span class="nw" title=${msg('Model switch')}>${sw}</span><br />` : nothing}${why ? html`${why}<br />` : nothing}${later
      ? html`<span class="later">${later}</span>`
      : nothing}`;
  };

  return [
    { id: 'ended', header: msg('Ended'), width: '64px', cell: (e) => html`<span class="jmono" title=${localTime(e.ts, true)}>${localTime(e.ts)}</span>` },
    {
      id: 'task',
      header: msg('Task'),
      width: 'minmax(130px,0.8fr)',
      rowHeader: true,
      text: (e) => e.key,
      cell: (e) => {
        const py = isPython(e);
        return html`<span class="jmono" title=${e.key}>${executorIcon(py, py ? msg('Python task') : msg('Agent task'), '')}
          ${kindUnit(e)}</span>`;
      },
    },
    {
      id: 'outcome',
      header: msg('Outcome'),
      tip: msg('How the attempt ended (stop)'),
      width: 'minmax(150px,0.7fr)',
      cell: (e) => {
        const ran = isLaunched(e);
        const numbered = ran && (tries.get(e.key)?.count ?? 1) > 1;
        const corrections = ran ? correctionsText((e.rounds ?? 1) - 1) : '';
        return statusWord({
          text: html`<span class="nw">${shortStop(e.stop)}</span>${numbered || corrections
            ? html`<span class="sub">${facts(numbered ? attemptLabel(e.attempt) : '', corrections)}</span>`
            : nothing}`,
          tone: stopTone(e.stop),
          cls: 'two',
          title: e.stop,
        });
      },
    },
    {
      id: 'agent',
      header: msg('Agent, model, identity'),
      width: 'minmax(150px,1fr)',
      cell: (e) =>
        html`<span class="jmono jdim two" title=${facts(e.route, modelSwitch(e.hops)) || nothing}>${isLaunched(e)
          ? html`<span>${[e.agent, e.model].filter(Boolean).join(' / ') || '—'}</span>${identity(e)}`
          : '—'}</span>`,
    },
    {
      id: 'tokens',
      header: msg('Tokens'),
      tip: msg('Input / output tokens, then cache read / cache write'),
      align: 'end',
      width: '92px',
      cell: (e) => {
        const u = e.usage;
        return html`<span class="two">${u
          ? html`<span>${tokenCount(u.input)} / ${tokenCount(u.output)}</span><span class="sub">${tokenCount(u.cache_read)} / ${tokenCount(u.cache_creation)}</span>`
          : html`<span class="jdim">—</span>`}</span>`;
      },
    },
    {
      id: 'cost',
      header: msg('Cost'),
      tip: msg('Reported by the coding agent'),
      align: 'end',
      width: '60px',
      cell: (e) => {
        const hops = e.hops ?? [];
        const perHop =
          hops.length > 1
            ? hops.map((h) => facts(h.model || h.route || '—', credentialLabel(h.credential) || '—', usd(h.cost_usd), stopLabel(h.stop))).join('\n')
            : '';
        return html`<span class="cost" title=${perHop || msg('Reported by the coding agent')}>${usd(e.cost_usd)}</span>`;
      },
    },
    {
      id: 'time',
      header: msg('Time'),
      align: 'end',
      width: '76px',
      cell: (e) => {
        const py = isPython(e);
        return isLaunched(e)
          ? html`${fmtDur(e.wall_s)}<span class="jdur"><i class=${isBad(e) ? 'bad' : py ? '' : 'llm'}
              style="width:${Math.max(2, Math.round((100 * (e.wall_s || 0)) / maxWall))}%"></i></span>`
          : '—';
      },
    },
    {
      id: 'reason',
      header: msg('Reason'),
      width: 'minmax(200px,2.2fr)',
      cell: (e) => {
        const unread = unreadEvents([e]);
        return html`<span class="jwhy" title=${e.reason || nothing}>${reason(e)}${unread
          ? html` <span class="unread nw" title=${msg(str`Event types from the coding agent that this contraagent version does not recognize: ${unread}`)}
              ><span aria-hidden="true">⚠</span> ${msg('Unrecognized events')}</span
            >`
          : nothing}</span>`;
      },
    },
  ];
}
