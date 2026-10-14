// The top of `ca-task-view`: the task's name and status, who ran it, what it
// spent, and a chip per finished attempt.
import { deferredIn, isLaunched, runReadings, runRelative, spendOf, tryQuota, type JournalRow, type Spend } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { toneAttr } from '@contraagent/elements';
import { pill } from '@contraagent/elements/primitives';
import { facts, fmtDur, kindUnit, listText, localTime, tokenCount, unreadEvents, usd } from '../../words/format.js';
import { attemptNames, deferredText, changedFiles, changedFilesTip, changeLabel, credentialLabel, credentialTip, locksLabel, locksTip, modelSwitch, outcomeLabel, stopLabel, type ChangeKind } from '../../words/index.js';
import { readingShort, readingTip } from '../../words/quota.js';
import { customColumnTip, customValues } from '../../words/row-extras.js';
import { type Tone } from '../../lib/tone.js';
import { executorIcon } from '../../words/executor.js';
import '@contraagent/elements/json-tree/define';
import { tagChips, type TranscriptTag } from '@contraagent/elements/transcript';
import { checkMessage } from '../../adapters/transcript/rounds.js';
import { agentLabel, launchWho, whoTags, type Who } from '../../adapters/transcript/who.js';
import { correctionsOf, hadSession, isPy, notStartedWhy, stateOf, type TaskContext } from './context.js';

/** Keys of `TaskDetail` the header shows itself; any other key (a `task_detail` callback's) is shown as JSON. */
const SHOWN_KEYS = new Set(['key', 'rows', 'launches', 'stream', 'task_detail_error', 'definition', 'io', 'row_extras']);

/** The status mark and the word a screen reader says for it. */
const mark = (ok: boolean) =>
  html`<span aria-hidden="true">${ok ? '✓' : '✕'}</span><span class="sr">${ok ? msg('passed') : msg('failed')}</span>`;

/** One line under the title: what happened to the task, in words, and its tone (`failed`, `attention`, `muted`, or none). */
function verdict(c: TaskContext): [text: string, tone: Tone] {
  const rows = c.detail.rows;
  const tries = rows.filter(isLaunched);
  const last = rows[rows.length - 1];
  const state = stateOf(c);
  switch (state) {
    case 'running':
      return [msg('Running'), 'neutral'];
    case 'waiting': {
      const node = c.plan?.nodes.find((n) => n.key === c.detail.key);
      const why = node?.deferred ? deferredText(node.deferred_cause, node.deferred, deferredIn(c.plan, node.deferred_cause)) : '';
      return why ? [msg(str`Not run: ${why}`), 'attention'] : [msg('Waiting'), 'muted'];
    }
    case 'skipped':
      return [msg('Skipped'), 'muted'];
    case 'not_started': {
      const cause = notStartedWhy(c);
      return [cause ? msg(str`Not started: ${cause}`) : msg('Not started'), 'attention'];
    }
    case 'failed': {
      const why = runRelative(last?.reason, c.run) || stopLabel(last?.stop);
      return [tries.length > 1 ? msg(str`Failed on all ${tries.length} attempts: ${why}`) : msg(str`Failed: ${why}`), 'failed'];
    }
    default:
      break;
  }
  if (!last) return [outcomeLabel(state), 'neutral'];
  const fails = tries.filter((r) => !r.ok);
  if (fails.length) {
    const why = runRelative(fails[0]?.reason, c.run) || stopLabel(fails[0]?.stop);
    return [
      fails.length === 1
        ? msg(str`Done on attempt ${tries.length} after 1 failed attempt. First failure: ${why}`)
        : msg(str`Done on attempt ${tries.length} after ${fails.length} failed attempts. First failure: ${why}`),
      'neutral',
    ];
  }
  const corrections = (last.rounds || 1) - 1 + (last.hook_errors ?? []).length;
  if (corrections > 0) {
    const errors = [...(last.hook_errors ?? []).flat(), ...(last.round_errors ?? []).flat(), ...c.rounds.flatMap((r) => r.rejectedWith)];
    const first = errors[0] ? checkMessage(runRelative(errors[0], c.run)) : '';
    if (!first) return [corrections === 1 ? msg('Done after 1 correction') : msg(str`Done after ${corrections} corrections`), 'neutral'];
    return [
      corrections === 1
        ? msg(str`Done after 1 correction. First failed check: ${first}`)
        : msg(str`Done after ${corrections} corrections. First failed check: ${first}`),
      'neutral',
    ];
  }
  const sw = modelSwitch(last.hops, null, last.skipped_hops);
  if (sw) return [msg(str`Done after a model switch: ${sw}`), 'neutral'];
  return [msg('Done'), 'neutral'];
}

/** The model of the latest round, as its launch named it (`--model`). */
function streamModel(c: TaskContext): string {
  for (let i = c.launches.length - 1; i >= 0; i--) {
    const l = c.launches[i];
    const m = l ? launchWho(l).model : '';
    if (m) return m;
  }
  return '';
}

/**
 * The header of task `key`. `onSearch(query, nth)` is called when the reader
 * picks one of its web searches (the nth with that query).
 */
export function taskHeader(c: TaskContext, key: string, onSearch: (query: string, nth: number) => void): TemplateResult {
  const d = c.detail;
  const live = c.live;
  const { rows, launches } = d;
  const py = isPy(d);
  const session = hadSession(d);
  const byTs = rows.slice().sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
  const lastRow = byTs[byTs.length - 1];
  const lc0 = launches[0];
  const who: Who = {
    agent: agentLabel(lc0?.cmd ? lc0.cmd.split(' ')[0] : lastRow?.agent),
    // The journal may not name the model (an agent that does not report it): fall back to the one the transcript shows.
    model: lc0?.model || lastRow?.model || streamModel(c),
    role: lc0?.role || '',
  };
  const otherModels = session ? [...new Set(byTs.map((r) => r.model).filter((x): x is string => !!x && x !== who.model))] : [];
  const first = rows[0];
  const tries = rows.filter(isLaunched);
  const extras = Object.entries(d).filter(([k]) => !SHOWN_KEYS.has(k));
  const [verdictText, tone] = verdict(c);
  const kindName = py ? msg('Python task') : msg('Agent task');
  const node = c.plan?.nodes.find((n) => n.key === d.key);
  return html`<div class="taskmeta">
      <div class="tm-head">
        ${executorIcon(py, kindName, `tm-av ${py ? 'py' : ''}`)}
        <div style="min-width:0">
          <div class="tm-name" title=${key}>${first ? kindUnit(first) : node ? kindUnit(node) : key.replace(/^python:/, '')} ${live ? pill({ text: msg('running'), tone: 'running' }) : nothing}</div>
          <div class="verdict" data-tone=${toneAttr(tone)}>${verdictText}</div>
          ${node?.claims?.length
            ? html`<div class="meta" title=${locksTip()}>
                ${locksLabel()} ${node.claims.map((text) => pill({ text }))}
              </div>`
            : nothing}
          ${session
            ? html`<div class="whos">
                ${tagChips([...whoTags(who), ...identityTags(tries)])}
                ${otherModels.length
                  ? html`<span class="meta">${otherModels.length === 1
                      ? msg(str`Earlier attempts used model ${otherModels[0] ?? ''}`)
                      : msg(str`Earlier attempts used models ${listText(otherModels)}`)}</span>`
                  : nothing}
              </div>`
            : nothing}
          ${launches.length
            ? html`<div class="meta">${launches.length === 1 ? msg('1 agent session running') : msg(str`${launches.length} agent sessions running`)}</div>`
            : nothing}
          ${spendLine(spendOf(rows))}
          ${quotaLine(c, tries)}
        </div>
      </div>
      ${tries.length
        ? html`<div class="runchips">${attemptNames(tries).map((name, i) => runChip(c, tries[i] as JournalRow, name, session, d.row_extras ?? []))}</div>`
        : nothing}
      ${customLine(tries, d.row_extras ?? [])}
      ${searchFold(tries, onSearch)}
      ${changesFold(tries)}
      ${unreadEvents(tries)
        ? html`<div class="meta unread" title=${msg('Event types from the coding agent that this contraagent version does not recognize')}>
            <span aria-hidden="true">⚠</span> ${msg(str`Unrecognized events: ${unreadEvents(tries)}`)}
          </div>`
        : nothing}
      ${d.task_detail_error ? html`<div class="meta v-bad">${msg(str`The task_detail callback failed: ${d.task_detail_error ?? ''}`)}</div>` : nothing}
      ${launches.map(
        (lc) => html`<details class="launch">
          <summary>${facts(msg(str`Process ${lc.pid ?? '—'}`), lc.key || '')}</summary>
          <div class="meta">${facts(msg(str`Plugin ${lc.plugin || msg('none', { id: 'none', desc: 'An empty value' })}`), msg(str`Model ${lc.model || '—'}`), msg(str`Role ${lc.role || msg('none', { id: 'none', desc: 'An empty value' })}`))}</div>
        </details>`,
      )}
      ${extras.map(
        ([k, v]) => html`<details class="io-fold"><summary>${k}</summary><cae-json-tree .value=${v}></cae-json-tree></details>`,
      )}
    </div>`;
}

/** The identities the task's attempts authenticated as (each hop's, when a model switch changed it). */
function identityTags(tries: JournalRow[]): TranscriptTag[] {
  const ids = [...new Set(tries.flatMap((r) => [...(r.hops ?? []).map((h) => h.credential), r.credential]).filter((x): x is string => !!x))];
  if (!ids.length) return [];
  const tip = [msg('What the coding agent authenticated as: an account or an API key (credential)'), ...ids.map(credentialTip)].filter(Boolean).join('\n');
  return [{ label: msg('identity'), value: listText(ids.map(credentialLabel)), tip, look: 'quiet' }];
}

/** The queries of the web searches the task's attempts made, in call order; each opens its card in the transcript. */
function searchFold(tries: JournalRow[], onSearch: (query: string, nth: number) => void) {
  const queries = tries.flatMap((r) => r.web_queries ?? []);
  const seen = new Map<string, number>();
  return queries.length
    ? html`<details class="io-fold">
        <summary>${queries.length === 1 ? msg('1 web search') : msg(str`${queries.length} web searches`)}</summary>
        <ol class="meta searches">
          ${queries.map((q) => {
            const nth = seen.get(q) ?? 0;
            seen.set(q, nth + 1);
            return html`<li><button class="qlink jmono" @click=${() => onSearch(q, nth)}>
              ${q}
            </button></li>`;
          })}
        </ol>
      </details>`
    : nothing;
}

/** The files each attempt changed under the task's `changes` patterns (the attempt named when more than one has them); nothing for a task that declares none. */
function changesFold(tries: JournalRow[]) {
  const names = attemptNames(tries);
  const withChanges = tries.filter((r) => r.changes).length;
  const files = tries.flatMap((r, i) => {
    const c = r.changes;
    if (!c) return [];
    const at = withChanges > 1 ? (names[i] ?? '') : '';
    const gone = new Set(c.removed);
    const of = (paths: string[] | undefined, kind: ChangeKind) => (paths ?? []).map((p) => facts(at, p, changeLabel(gone.has(p) ? 'removed' : kind)));
    return [...of(c.created, 'created'), ...of(c.modified, 'modified'), ...of(c.deleted, 'deleted')];
  });
  if (!withChanges) return nothing;
  if (!files.length) return html`<div class="meta">${msg('No changed files')}</div>`;
  return html`<details class="io-fold">
    <summary title=${changedFilesTip()}>${changedFiles(files.length)}</summary>
    <ul class="meta searches jmono">${files.map((f) => html`<li>${f}</li>`)}</ul>
  </details>`;
}

/** The latest attempt's custom columns (`row_extras`), name and value; each attempt's are in its chip's tooltip. */
function customLine(tries: JournalRow[], extras: readonly string[]) {
  const last = tries[tries.length - 1];
  const values = last ? customValues(last, extras) : [];
  if (!values.length) return nothing;
  const tip = customColumnTip();
  return html`<div class="whos">${tagChips(values.map(([label, value]) => ({ label, value, tip, look: 'quiet' as const })))}</div>`;
}

/** The task's spend over all its attempts: cost, then tokens. Nothing when none was reported. */
function spendLine(s: Spend | null) {
  if (!s) return nothing;
  return html`<div class="spend">
    <b title=${msg('Reported by the coding agent')}>${usd(s.cost)}</b>
    <span>${msg(str`Tokens: ${tokenCount(s.input)} input, ${tokenCount(s.output)} output, ${tokenCount(s.cache_read)} cache read, ${tokenCount(s.cache_creation)} cache write`)}</span>
    <span>${s.calls === 1 ? msg('1 API call') : msg(str`${s.calls} API calls`)}</span>
  </div>`;
}

/** The task's subscription usage: at its first session start, and the next reading the run took after it ended. */
function quotaLine(c: TaskContext, tries: JournalRow[]) {
  const readings = runReadings(c.journal.length ? c.journal : tries);
  const first = tries[0];
  const last = tries[tries.length - 1];
  const start = first ? tryQuota(first, readings).start : null;
  if (!start || !last) return nothing;
  const next = tryQuota(last, readings).next;
  // The identity chip names the account; both readings are that account's.
  return html`<div class="spend quota">
    <span title=${readingTip(start)}>${msg(str`Usage at session start: ${readingShort(start)}`)}</span>
    ${next ? html`<span title=${readingTip(next)}>${msg(str`Usage after this task: ${readingShort(next)}`)}</span>` : nothing}
  </div>`;
}

/** One finished attempt: how it ended, how long, its cost; the rest (when, corrections, model, model switch) in its tooltip. */
function runChip(c: TaskContext, r: JournalRow, name: string, session: boolean, extras: readonly string[]) {
  const ok = r.ok;
  const reason = runRelative(r.reason, c.run);
  const sw = modelSwitch(r.hops, null, r.skipped_hops);
  const tip = [
    msg(str`Ended ${localTime(r.ts, true)}`),
    correctionsOf(r),
    session && r.model ? msg(str`Model ${r.model}`) : '',
    sw ? msg(str`Model switch: ${sw}`) : '',
    reason,
    r.route || '',
    ...customValues(r, extras).map(([k, v]) => `${k}: ${v}`),
  ]
    .filter(Boolean)
    .join('\n');
  const cost = r.cost_usd !== null && r.cost_usd !== undefined ? usd(r.cost_usd) : '';
  return html`<span class="runchip ${ok ? 'ok' : 'bad'}" title=${tip}>
    ${mark(ok)} ${facts(name, stopLabel(r.stop, r.reason), fmtDur(r.wall_s), cost)}
  </span>`;
}
