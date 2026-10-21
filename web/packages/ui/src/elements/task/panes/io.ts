// The input and output panes of `ca-task-view`: what the task read (parameters,
// files, earlier tasks, the prompt) and what it wrote (files against their
// contracts, the outcome, tokens and cost, later tasks).
import {
  isLaunched,
  isPython,
  runReadings,
  runRelative,
  runStarts,
  tryQuota,
  type DownstreamTask,
  type JournalRow,
  type Lineage,
  type Outcome,
  type SourcedReading,
  type TaskInputFile,
} from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { pill } from '@contraagent/elements/primitives';
import '@contraagent/elements/json-tree/define';
import { facts, fmtDur, kindUnit, tokenCount, usd } from '../../../words/format.js';
import { attemptLabel, attemptNames, credentialLabel, credentialTip, outcomeLabel, stopLabel } from '../../../words/index.js';
import { accountReading, readingShort, readingTip } from '../../../words/quota.js';
import { outcomeMark, outcomeTone, stopTone } from '../../../lib/tone.js';
import { executorIcon } from '../../../words/executor.js';
import { promptText } from '../../shared/prompt-text.js';
import { contractChip } from '../../shared/contract-parts.js';
import { ioFileCard } from '../../shared/file-card.js';
import { taskChip } from '../../shared/task-chip.js';
import { inputView, notPassed, type EarlierTask, type InputFile } from '../inputs.js';
import { roundLabel, roundWhy } from '../../../words/rounds.js';
import { inputFileCheckWord, inputRootPath, inputRootTip, lineageTip, lineageWord } from '../../../words/lineage.js';
import { correctionsOf, hadSession, isPy, producerOf, stateOf, taskLink, type TaskContext } from '../context.js';

const valueText = (v: unknown): string => (typeof v === 'string' ? v : JSON.stringify(v) ?? String(v));
const sameJson = (a: unknown, b: unknown): boolean => {
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
};

/** A task's outcome as a pill, in its words. */
const outcomeChip = (o: Outcome) => pill({ text: outcomeLabel(o), tone: outcomeTone(o), mark: outcomeMark(o) });

/**
 * What the task read: its parameters, its input files (`InputFile` params), the files
 * an input contract checks before it starts, the earlier tasks, and (for an agent task)
 * its prompt.
 */
export function inputPane(c: TaskContext): TemplateResult {
  const d = c.detail;
  const io = d.io;
  const params = Object.entries(io.params);
  const { files, earlier } = inputView(io);
  const source = (v: unknown) => io.upstream.find((u) => u.outputs.some((o) => o.file.exists && sameJson(o.file.content, v)));
  return html`<h4 class="sect-h">${msg('Parameters')}</h4>
    ${params.length
      ? html`<table class="ct-fields params">
          ${params.map(([k, v]) => {
            const from = source(v);
            return html`<tr>
              <td class="jmono">${k}</td>
              <td>${v !== null && typeof v === 'object' ? html`<cae-json-tree .value=${v} .open=${0}></cae-json-tree>` : html`<span class="jmono">${valueText(v)}</span>`}</td>
              <td>${from ? html`<span class="from">${msg(html`From ${taskLink(c, from)}`)}</span>` : nothing}</td>
            </tr>`;
          })}
        </table>`
      : html`<div class="meta">${msg('No parameters')}</div>`}
    <h4 class="sect-h">${msg('Input files')}</h4>
    ${io.input_files?.length ? io.input_files.map((f) => inputFileCard(c, f)) : html`<div class="meta">${msg('No input files')}</div>`}
    ${files.length
      ? html`<h4 class="sect-h">${msg('Checked files it reads')}</h4>
          ${files.map((f) => inputCard(c, f))}`
      : nothing}
    <h4 class="sect-h">${msg('Earlier tasks')}</h4>
    ${earlier.length ? earlier.map((e) => earlierTask(c, e)) : html`<div class="meta">${msg('No earlier tasks')}</div>`}
    ${isPy(d) ? nothing : promptSection(c)}`;
}

/**
 * One input file of the task (an `InputFile` param): its check at the start, its path
 * (with its input root), the param that holds it, its hash, and the earlier task whose
 * output file it is.
 */
function inputFileCard(c: TaskContext, f: TaskInputFile) {
  const tone = f.check === 'passed' ? 'done' : f.check === 'refused' ? 'failed' : 'neutral';
  const mark = f.check === 'passed' ? 'done' : f.check === 'refused' ? 'failed' : 'pending';
  const writer = f.writer ? (c.detail.io.upstream.find((u) => u.key === f.writer) ?? c.outcomes.get(f.writer)) : undefined;
  const origin = f.writer
    ? html`<span>${msg(html`Output of ${taskLink(c, writer ?? { key: f.writer, kind: f.writer, unit: '' })}`)}</span>`
    : nothing;
  const rooted = inputRootPath(f);
  const tip = f.root && f.root !== 'out' ? inputRootTip(f.root, f.path) : f.path;
  return html`<div class="io-card one infile">
    <div class="io-hd">${pill({ text: inputFileCheckWord(f.check), tone, mark })}<span class="jmono ct-path" title=${tip}>${rooted ?? runRelative(f.path, c.run)}</span></div>
    <div class="meta io-from"><span title=${f.sha256}>${facts(msg(str`Param ${f.param}`), `sha256 ${f.sha256.slice(0, 12)}`)}</span>${f.writer
      ? html` | ${origin}`
      : nothing}</div>
    ${f.reason ? html`<div class="meta err">${f.reason}</div>` : nothing}
  </div>`;
}

/** One file an input contract checks before the task starts: its check, and the earlier task that writes it or that it is from before the run. */
function inputCard(c: TaskContext, f: InputFile) {
  const u = f.from;
  const state = u ? c.outcomes.get(u.key)?.outcome : undefined;
  const origin = u
    ? html`<span>${msg(html`Output of ${taskLink(c, u)}`)}</span>${state && state !== 'done' ? outcomeChip(state) : nothing}`
    : msg('File from before the run');
  // Written by an earlier task: that task's check of it ("passed", "not written (task failed)").
  const st = f.out?.status;
  if (!st) return ioFileCard(f.spec, 'input', c.run, { origin });
  const chip = contractChip(st);
  return ioFileCard({ ...f.spec, status: st }, 'input', c.run, { origin, chip });
}

/**
 * One earlier task: its status, how this task is joined to it (its lineage, in the words of
 * the graph's edges), how many of its output files this task reads, and the others folded
 * under it (open when one did not pass).
 */
function earlierTask(c: TaskContext, e: EarlierTask) {
  const u = e.task;
  const kindName = isPython(u) ? msg('Python task') : msg('Agent task');
  const state = c.outcomes.get(u.key)?.outcome;
  const n = u.outputs.length;
  const summary = !n
    ? msg('No output files')
    : facts(n === 1 ? msg('1 output file') : msg(str`${n} output files`), e.read ? (e.read === 1 ? msg('1 read by this task') : msg(str`${e.read} read by this task`)) : '');
  const head = html`<div class="up-hd">
    ${executorIcon(isPython(u), kindName)}
    ${taskLink(c, u)}
    ${state ? outcomeChip(state) : nothing}
    ${lineageTags(u.lineage ?? [])}
    <span class="meta">${summary}</span>
  </div>`;
  if (!e.rest.length) return html`<div class="upstream">${head}</div>`;
  const cards = e.rest.map((o) => ioFileCard(o, 'output', c.run, { producerOf: producerOf(c) }));
  return e.rest.some(notPassed)
    ? html`<div class="upstream">${head}${cards}</div>`
    : html`<details class="upstream"><summary>${head}</summary>${cards}</details>`;
}

/** The prompt of the round chosen in the transcript, or why there is none. */
function promptSection(c: TaskContext) {
  const d = c.detail;
  const n = c.launches.length;
  const shown = c.shownRound;
  const info = c.rounds[shown];
  const tries = c.rounds[c.rounds.length - 1]?.tryNo ?? 1;
  const ran = d.rows.filter(isLaunched);
  const names = attemptNames(ran);
  const starts = runStarts(ran);
  const prompt = c.launches[shown]?.prompt ?? '';
  const state = stateOf(c);
  return html`<h4 class="sect-h">${msg('Prompt')}${n > 1 && info
      ? html` <span class="meta">${roundLabel(info, tries, names[info.tryNo - 1])}: ${roundWhy(info, starts[info.tryNo - 1] !== starts[info.tryNo - 2])}</span>`
      : nothing}</h4>
    ${prompt
      ? promptText(prompt)
      : html`<div class="meta">${d.stream
          ? msg('Loading…')
          : hadSession(d)
            ? facts(msg('No prompt'), msg('not saved (keep_transcripts = false)'))
            : facts(msg('No prompt'), outcomeLabel(state))}</div>`}`;
}

/** Per attempt that reported any: tokens, API calls, cost and identity; per hop under a model switch. */
function usageTable(c: TaskContext, rows: JournalRow[]) {
  const spent = rows.filter((r) => isLaunched(r) && (r.usage || (r.cost_usd !== null && r.cost_usd !== undefined)));
  if (!spent.length) return nothing;
  const dash = html`<td class="jdim">—</td>`;
  const readings: SourcedReading[] = runReadings(c.journal.length ? c.journal : rows);
  const quota = spent.some((r) => (r.quota ?? []).length);
  const dashL = html`<td class="l jdim">—</td>`;
  // The identity column is next to it: name the account only when the reading is another one's.
  const reading = (q: ReturnType<typeof tryQuota>['start'], cred: string | undefined) =>
    q ? html`<td class="l" title=${readingTip(q)}>${(q.credential ?? '') === (cred ?? '') ? readingShort(q) : accountReading(q)}</td>` : dashL;
  return html`<h4 class="sect-h">${msg('Tokens and cost')}</h4>
    <div class="usage-wrap" data-scroll="x"><table class="usage">
      <tr>
        <th class="l"></th><th>${msg('Input')}</th><th>${msg('Output', { id: 'tokens-output', desc: 'Column: output tokens' })}</th><th>${msg('Cache read')}</th><th>${msg('Cache write')}</th>
        <th>${msg('API calls')}</th><th title=${msg('Reported by the coding agent')}>${msg('Cost')}</th><th class="l">${msg('Identity')}</th>
        ${quota
          ? html`<th class="l" title=${msg('Subscription usage when the agent session started (account-wide)')}>${msg('Usage at start')}</th>
              <th class="l" title=${msg('The first reading of the same account after this attempt ended')}>${msg('Usage after')}</th>`
          : nothing}
      </tr>
      ${spent.map((r) => {
        const u = r.usage;
        const hops = r.hops ?? [];
        return html`<tr>
            <td class="l">${attemptLabel(r.attempt)}</td>
            ${u
              ? html`<td>${tokenCount(u.input)}</td><td>${tokenCount(u.output)}</td><td>${tokenCount(u.cache_read)}</td><td>${tokenCount(u.cache_creation)}</td><td>${u.calls}</td>`
              : html`${dash}${dash}${dash}${dash}${dash}`}
            <td>${usd(r.cost_usd)}</td><td class="l" title=${credentialTip(r.credential) || nothing}>${credentialLabel(r.credential) || '—'}</td>
            ${quota ? html`${reading(tryQuota(r, readings).start, r.credential)}${reading(tryQuota(r, readings).next, r.credential)}` : nothing}
          </tr>
          ${hops.length > 1
            ? hops.map(
                (h) => html`<tr class="hop">
                  <td class="l">${facts(h.model || h.route || '—', stopLabel(h.stop))}</td>
                  <td></td><td></td><td></td><td></td><td></td>
                  <td>${usd(h.cost_usd)}</td><td class="l" title=${credentialTip(h.credential) || nothing}>${credentialLabel(h.credential) || '—'}</td>
                  ${quota ? html`<td></td><td></td>` : nothing}
                </tr>`,
              )
            : nothing}`;
      })}
    </table></div>`;
}

/** What the task wrote: its output files, its outcome, tokens and cost, and the later tasks. */
export function outputPane(c: TaskContext): TemplateResult {
  const d = c.detail;
  const io = d.io;
  const last = d.rows[d.rows.length - 1];
  // The reason, a refusal's cause and a model switch are in the verdict above, so they are not repeated here.
  return html`<h4 class="sect-h">${msg('Output files')}</h4>
    ${io.outputs.length
      ? io.outputs.map((o) => ioFileCard(o, 'output', c.run, { producerOf: producerOf(c) }))
      : html`<div class="meta">${msg('No output files')}</div>`}
    ${last
      ? html`<h4 class="sect-h">${msg('Outcome')}</h4>
          <div class="ct-in">
            ${pill({ text: stopLabel(last.stop, last.reason), tone: stopTone(last.stop) })}
            ${isLaunched(last) ? html`<span class="meta">${facts(attemptLabel(last.attempt), fmtDur(last.wall_s), correctionsOf(last))}</span>` : nothing}

          </div>`
      : nothing}
    ${usageTable(c, d.rows)}
    <h4 class="sect-h">${msg('Later tasks')}</h4>
    ${io.downstream.length ? laterTasks(c, io.downstream) : html`<div class="meta">${msg('No later tasks')}</div>`}`;
}

/** A task's lineage as tags, in the words of the graph's edges, each with the field it comes from as its tooltip. */
function lineageTags(lineage: readonly Lineage[]) {
  return lineage.map((l) => html`<span class="lineage" data-lineage=${l} title=${lineageTip(l)}>${lineageWord(l)}</span>`);
}

/**
 * The later tasks, a row of chips per lineage (by the strongest each has): given output,
 * runs after, created after result; one row without a tag for those an export written
 * before lineage holds.
 */
function laterTasks(c: TaskContext, down: readonly DownstreamTask[]) {
  const order: Lineage[] = ['given_from', 'after', 'created_from'];
  const first = (x: DownstreamTask): Lineage | null => order.find((l) => (x.lineage ?? []).includes(l)) ?? null;
  return [...order, null]
    .map((l) => [l, down.filter((x) => first(x) === l)] as const)
    .filter(([, xs]) => xs.length)
    .map(([l, xs]) => html`<div class="down">${l ? lineageTags([l]) : nothing}${xs.map((x) => taskChip(c.host, kindUnit(x), x))}</div>`);
}
