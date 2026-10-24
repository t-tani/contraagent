// The history's columns (`ca-journal-table`): a row per finished attempt
// (`JournalRow`), when it ended, the task, its stop, the agent and model, tokens,
// cost, time and the reason, then the pipeline's own columns (`row_extras`).
import { isBad, isLaunched, isPython, runRelative, type JournalRow, type TaskOutcome } from '@contraagent/api';
import type { DataColumn } from '@contraagent/elements/data-table';
import { statusWord } from '@contraagent/elements/primitives';
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { stopTone } from '../lib/tone.js';
import { executorIcon } from '../words/executor.js';
import { facts, fmtDur, kindUnit, localTime, sentence, tokenCount, unreadEvents, usageUnknown, usageUnknownWords, usd } from '../words/format.js';
import { attemptLabel, correctionsText, credentialLabel, credentialTip, modelSwitch, notStartedCause, outcomeLabel, replayedLabel, replayedTip, stopLabel } from '../words/index.js';
import { accountReading, readingShort } from '../words/quota.js';
import { customColumnTip, customValue } from '../words/row-extras.js';
import { contextWarnedText, contextWarnedTip, peakContextLine } from '../words/context.js';
import { safetyStopCount, safetyStopLine, safetyStopTip } from '../words/safety.js';
import { attemptFacts, correctionCount } from './filters.js';

export interface JournalColumnsContext {
  /** The run id: paths inside the run directory are shown relative to it. */
  run: string;
  /** What happened to each task (`deriveRun`): a refused row names its cause in words. */
  outcomes: ReadonlyMap<string, TaskOutcome>;
  /** Every row of the journal, in order: the attempts of a task, and the one that later did it. */
  journal: readonly JournalRow[];
  /** The rows shown: the time bars are relative to their longest. */
  rows: readonly JournalRow[];
  /** The pipeline's own columns (`RunSummary.row_extras`): one column each, after the reason. */
  extras?: readonly string[];
  /** Mark each attempt played from its recording (`JournalRow.replayed`): the run is a replay that also launched (`mixedReplay`). */
  replayMarks?: boolean;
}

/** A stop as a short column label: a task that never ran is just "not started"; the cause goes to the reason. */
export function shortStop(stop: string | null | undefined): string {
  return stop === 'invalid_input' ? outcomeLabel('not_started') : stopLabel(stop);
}

/** The identities an attempt authenticated as, in order; both when a model switch changed it. */
const identities = (e: JournalRow): string[] => [...new Set([...(e.hops ?? []).map((h) => h.credential), e.credential].filter((c): c is string => !!c))];

/** The one identity every attempt that ran authenticated as alone; '' when they differ or none is known. */
export function sharedIdentity(journal: readonly JournalRow[]): string {
  const seen = new Set(journal.filter(isLaunched).map((e) => identities(e).join('\n')));
  const [only] = seen;
  return seen.size === 1 && only && !only.includes('\n') ? only : '';
}

/** The identity the attempt authenticated as (both when a model switch changed it), unless `shared`: then the column's header names it. */
function identity(e: JournalRow, shared: string) {
  const ids = identities(e);
  if (!ids.length) return nothing;
  // The subscription usage the attempt's first session started at, when the agent reported one.
  const start = (e.quota ?? [])[0];
  const tip = start ? msg(str`Usage at session start (account-wide): ${accountReading(start)}`) : '';
  // The reading belongs to one account: name it when the row has more than one, or a different one.
  const own = start && ids.length === 1 && (start.credential ?? '') === ids[0];
  const shown = start ? (own ? readingShort(start) : accountReading(start)) : '';
  const tips = [tip, ...ids.map(credentialTip)].filter(Boolean).join('\n');
  if (shared) return start ? html`<span class="sub" title=${tips || nothing}><span class="q">${shown}</span></span>` : nothing;
  return html`<span class="sub" title=${tips || nothing}>${ids.map((c) => credentialLabel(c)).join(' → ')}${start ? html` <span class="q">${shown}</span>` : nothing}</span>`;
}

/** The columns of the history. */
export function journalColumns(ctx: JournalColumnsContext): DataColumn<JournalRow>[] {
  const maxWall = Math.max(1, ...ctx.rows.map((e) => e.wall_s || 0));
  const tries = attemptFacts(ctx.journal);
  const index = new Map(ctx.journal.map((r, i) => [r, i]));
  // Every attempt ran as one identity: the header names it once, the rows do not.
  const shared = sharedIdentity(ctx.journal);
  /** The attempt that later did the task, after this one failed (0: none). */
  const laterTry = (e: JournalRow): number => {
    const f = tries.get(e.key);
    return !e.ok && isLaunched(e) && (f?.lastOk ?? -1) > (index.get(e) ?? 0) ? (f?.lastOkTry ?? 0) : 0;
  };

  /**
   * What the reason column says: the model switch, then (for a row that failed,
   * never ran, or was partly done) the reason, run-relative, then the attempt that later did the task,
   * then its peak context when it passed the warning threshold of the context limit.
   */
  const reason = (e: JournalRow) => {
    const ran = isLaunched(e);
    const sw = modelSwitch(e.hops, null, e.skipped_hops);
    const run = ctx.run || e.run_id || '';
    const own = ctx.outcomes.get(e.key);
    const cause = e.stop === 'invalid_input' && own ? notStartedCause({ attempts: [e], cause: null }, ctx.outcomes, run) : '';
    const why = cause ? sentence(cause) : (!e.ok || !ran || e.stop === 'partial') && e.reason ? runRelative(e.reason, run) : '';
    const n = laterTry(e);
    const later = n ? msg(str`Task done on attempt ${n}`) : '';
    const warned = e.context_warned ? contextWarnedText(e) : '';
    if (!sw && !why && !later && !warned) return html`<span class="jdim">—</span>`;
    return html`${sw ? html`<span class="nw" title=${msg('Model switch')}>${sw}</span><br />` : nothing}${why ? html`${why}<br />` : nothing}${later
      ? html`<span class="later">${later}</span>${warned ? html`<br />` : nothing}`
      : nothing}${warned
      ? html`<span class="tone-text" data-tone="attention" title=${[contextWarnedTip(), peakContextLine(e)].filter(Boolean).join('\n')}>${warned}</span>`
      : nothing}`;
  };

  /** A pipeline's own column: its name as the pipeline wrote it, its value as text. */
  const custom = (name: string): DataColumn<JournalRow> => ({
    id: `x:${name}`,
    header: name,
    tip: customColumnTip(),
    width: 'minmax(80px,0.6fr)',
    text: (e) => customValue((e as Record<string, unknown>)[name]),
    cell: (e) => {
      const v = customValue((e as Record<string, unknown>)[name]);
      return v === '—' ? html`<span class="jdim">—</span>` : html`<span class="jmono" title=${v}>${v}</span>`;
    },
  });

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
        const corrections = ran ? correctionsText(correctionCount(e)) : '';
        const played = ctx.replayMarks && e.replayed ? replayedLabel() : '';
        return statusWord({
          text: html`<span class="nw">${shortStop(e.stop)}</span>${numbered || corrections || played
            ? html`<span class="sub" title=${played ? replayedTip() : nothing}>${facts(numbered ? attemptLabel(e.attempt) : '', corrections, played)}</span>`
            : nothing}`,
          tone: stopTone(e.stop),
          cls: 'two',
          title: e.stop,
        });
      },
    },
    {
      id: 'agent',
      header: shared ? msg('Agent, model') : msg('Agent, model, identity'),
      ...(shared ? { tip: [msg(str`Identity: ${credentialLabel(shared)}`), credentialTip(shared)].filter(Boolean).join('\n') } : {}),
      width: 'minmax(150px,1fr)',
      cell: (e) =>
        html`<span class="jmono jdim two" title=${facts(e.route, modelSwitch(e.hops, null, e.skipped_hops)) || nothing}>${isLaunched(e)
          ? html`<span>${[e.agent, e.model].filter(Boolean).join(' / ') || '—'}</span>${identity(e, shared)}`
          : '—'}</span>`,
    },
    {
      id: 'tokens',
      header: msg('Tokens'),
      tip: msg('Input / output | cache read / cache write'),
      align: 'end',
      width: '92px',
      cell: (e) => {
        const u = e.usage;
        const tip = [u?.resident != null ? msg(str`Input of the first API call: ${tokenCount(u.resident)}`) : '', peakContextLine(e)].filter(Boolean).join('\n');
        const first = tip || nothing;
        return html`<span class="two" title=${first}>${u
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
        const unknown = usageUnknownWords(usageUnknown([e]));
        const stops = e.safety_stops ?? [];
        return html`<span class="jwhy" title=${e.reason || nothing}>${reason(e)}${stops.length
          ? html` <span class="tone-text nw" data-tone="attention" title=${[safetyStopTip(), ...stops.map(safetyStopLine)].join('\n')}
              >${safetyStopCount(stops.length)}</span
            >`
          : nothing}${unread
          ? html` <span class="unread nw" title=${msg(str`Events this contraagent version could not read (unread_events): ${unread}`)}
              ><span aria-hidden="true">⚠</span> ${msg('Unrecognized events')}</span
            >`
          : nothing}${unknown
          ? html` <span class="unread nw" title=${unknown.tip}><span aria-hidden="true">⚠</span> ${unknown.label}</span>`
          : nothing}</span>`;
      },
    },
    ...(ctx.extras ?? []).map(custom),
  ];
}
