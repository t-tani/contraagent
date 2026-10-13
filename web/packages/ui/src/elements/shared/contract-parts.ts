// A contract file read the way a person checks it: each field of its schema
// against what the file holds. Templates shared by the outputs view and a task's
// input/output view; their classes are in `contractStyles`.
import type { ContractSpec, ContractStatus, FileView, Outcome } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { css, html, nothing, type TemplateResult } from 'lit';
import { inputCause, inputProblems, runRelative } from '../../lib/labels.js';
import { facts, localTime, sentence } from '../../lib/format.js';
import './ca-json-tree.js';

/** A contract status in words, in the current locale. */
export function contractStatusLabel(s: ContractStatus): string {
  switch (s) {
    case 'valid':
      return msg('passed');
    case 'invalid':
      return msg('failed checks');
    case 'refused':
      return msg('not written (task not started)');
    case 'failed':
      return msg('not written (task failed)');
    case 'running':
      return msg('not written yet (task running)');
    case 'pending':
      return msg('not written yet (task waiting)');
  }
}

/** Why a contract has its status, in the current locale. */
export function contractStatusWhy(s: ContractStatus): string {
  switch (s) {
    case 'refused':
      return msg('The task did not start because an input was missing or failed checks');
    case 'valid':
      return msg('The file passed its checks');
    case 'invalid':
      return msg('The file failed its checks');
    case 'failed':
      return msg('The task failed before it wrote a file that passes its checks');
    case 'running':
      return msg('The task is running');
    case 'pending':
      return msg('The task is waiting');
  }
}

/** What a correction is, for tooltips. */
export const correctionTip = (): string => msg('Correction: another round in the same agent session after the output failed checks');

/** How many corrections a file took (`rounds` counts the first round too), in words; '' for none. */
export function correctionsLabel(rounds: number | null | undefined, passed: boolean): string {
  const n = (rounds ?? 1) - 1;
  if (n < 1) return '';
  if (passed) return n === 1 ? msg('after 1 correction') : msg(str`after ${n} corrections`);
  return n === 1 ? msg('1 correction') : msg(str`${n} corrections`);
}

/** A ✓ or ✕ with its word for screen readers (the word is also in the row). */
const fieldMark = (ok: boolean, word: string, tip = '') =>
  html`<span class="fk ${ok ? 'ok' : 'bad'}" title=${tip || nothing}><span aria-hidden="true">${ok ? '✓' : '✕'}</span> ${word}</span>`;

/** An input file's state: found, or missing (and whether the task needed it). */
export function inputChip(o: ContractSpec): TemplateResult {
  const ok = !!o.file.exists;
  const text = ok ? msg('found') : o.required ? msg('missing (required)') : msg('missing (optional)');
  return html`<span class="ct-chip ${ok ? 'valid' : o.required ? 'invalid' : 'pending'}">${text}</span>`;
}

const STATUSES: readonly ContractStatus[] = ['valid', 'invalid', 'refused', 'failed', 'running', 'pending'];

/** `contractStatusLabel` as a record (read at render time: each value is a getter). */
export const CONTRACT_STATUS_LABEL = Object.defineProperties(
  {},
  Object.fromEntries(STATUSES.map((k) => [k, { enumerable: true, get: () => contractStatusLabel(k) }])),
) as Readonly<Record<ContractStatus, string>>;

/** `contractStatusWhy` as a record (read at render time: each value is a getter). */
export const CONTRACT_STATUS_WHY = Object.defineProperties(
  {},
  Object.fromEntries(STATUSES.map((k) => [k, { enumerable: true, get: () => contractStatusWhy(k) }])),
) as Readonly<Record<ContractStatus, string>>;

/** The journal stop a contract status reads as, for colouring. */
export const statusStop = (s: ContractStatus | null | undefined): string =>
  s === 'invalid' ? 'invalid_output' : s === 'refused' ? 'invalid_input' : 'error';

function typeOk(t: string, v: unknown): boolean {
  if (t.startsWith('list[') || t === 'array') return Array.isArray(v);
  if (t === 'string') return typeof v === 'string';
  if (t === 'integer') return Number.isInteger(v);
  if (t === 'number') return typeof v === 'number';
  if (t === 'boolean') return typeof v === 'boolean';
  if (t === 'object') return v !== null && typeof v === 'object' && !Array.isArray(v);
  return true; // a type the table cannot judge: leave it to the model's own check
}

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

function shortValue(v: unknown): TemplateResult {
  if (v === undefined) return html`<span class="jdim">—</span>`;
  if (typeof v === 'string') return html`<span class="js" title=${v}>"${cut(v, 90)}"</span>`;
  if (Array.isArray(v)) {
    const head = v
      .slice(0, 3)
      .map((x) => (typeof x === 'string' ? `"${cut(x, 28)}"` : JSON.stringify(x)))
      .join(', ');
    return html`<span class="jn">${v.length === 1 ? msg('1 item') : msg(str`${v.length} items`)}</span>
      <span class="jdim">${head}${v.length > 3 ? ', …' : ''}</span>`;
  }
  if (v !== null && typeof v === 'object')
    return html`<span class="jn">${msg('object')}</span> <span class="jdim">${Object.keys(v).slice(0, 4).join(', ')}</span>`;
  return html`<span class="jn">${JSON.stringify(v)}</span>`;
}

/** The file's content as a tree, or as text when it is not JSON. */
export function fileContent(f: FileView): TemplateResult {
  const c = f.content;
  return c !== null && typeof c === 'object'
    ? html`<ca-json-tree .value=${c}></ca-json-tree>`
    : html`<pre class="jtree">${typeof c === 'string' ? c : msg('Not JSON')}</pre>`;
}

/** A `RootModel[str]`-style schema: the model wraps one value of the given type. */
const rootOf = (name: string): string | null => /^RootModel\[(.+)\]$/.exec(name)?.[1] ?? null;

/** The contract on the left of each row, the file's value on the right, a verdict per field. */
export function fieldCheckTable(o: ContractSpec): TemplateResult {
  const f = o.file;
  const c = f.content;
  // A text result (a text file, or one JSON value) has no fields to check: show the file itself.
  if (!o.fields.length && (o.schema_name === 'text' || rootOf(o.schema_name) !== null)) {
    return f.exists
      ? html`<details class="ct-raw">
          <summary>${wholeFile(f)}</summary>
          ${fileContent(f)}
        </details>`
      : html``;
  }
  // No file: the fields it must have, and nothing to check them against; its status chip says it is not there.
  if (!f.exists) {
    return o.fields.length
      ? html`<table class="ct-check">
          <tr><th>${msg('Field')}</th><th>${msg('Expected')}</th></tr>
          ${o.fields.map(
            (x) => html`<tr>
              <td class="jmono">${x.name}</td>
              <td class="jmono jdim">${x.type}${x.required ? nothing : html` <i>${msg('optional')}</i>`}</td>
            </tr>`,
          )}
        </table>`
      : html``;
  }
  const obj = c !== null && typeof c === 'object' && !Array.isArray(c) ? (c as Record<string, unknown>) : null;
  const rows = o.fields.map((x) => {
    let mark: TemplateResult = html``;
    let val: unknown;
    if (obj) {
      const has = x.name in obj;
      val = has ? obj[x.name] : undefined;
      if (!has)
        mark = x.required
          ? fieldMark(false, msg('missing'), msg('A required field that is not in the file'))
          : html`<span class="fk none">${msg('absent (optional)')}</span>`;
      else
        mark = typeOk(x.type, val) ? fieldMark(true, msg('passed')) : fieldMark(false, msg('wrong type'), msg(str`Expected ${x.type}`));
    }
    return html`<tr>
      <td class="jmono">${x.name}</td>
      <td class="jmono jdim">${x.type}${x.required ? nothing : html` <i>${msg('optional')}</i>`}</td>
      <td>${shortValue(val)}</td>
      <td>${mark}</td>
    </tr>`;
  });
  const extra = obj ? Object.keys(obj).filter((k) => !o.fields.some((x) => x.name === k)) : [];
  return html`<table class="ct-check">
      <tr><th>${msg('Field')}</th><th>${msg('Expected')}</th><th>${msg('In the file')}</th><th>${msg('Check')}</th></tr>
      ${rows}
      ${extra.map(
        (k) => html`<tr>
          <td class="jmono">${k}</td><td class="jdim">${msg('not in the schema')}</td><td>${shortValue(obj?.[k])}</td>
          <td><span class="fk warn" title=${msg('Not in the schema')}>${msg('extra field')}</span></td>
        </tr>`,
      )}
    </table>
    ${!obj ? html`<div class="meta note">${msg('Not a JSON object')}</div>` : nothing}
    <details class="ct-raw">
      <summary>${wholeFile(f)}</summary>
      ${fileContent(f)}
    </details>`;
}

/** The fold over a file's content: `Whole file | 1204 B | written Oct 12, 10:38:40`. */
const wholeFile = (f: FileView): string =>
  facts(msg('Whole file'), `${f.size ?? 0} B`, f.mtime ? msg(str`written ${localTime(f.mtime, true)}`) : '', f.truncated ? msg('truncated') : '');

/**
 * The schema as the reader names it: the class name for a model, "text" for a
 * text result. The class name stays in the tooltip.
 */
export function schemaName(o: ContractSpec): TemplateResult {
  const root = rootOf(o.schema_name);
  const shown = o.schema_name === 'text' || root === 'str' ? msg('text') : root ?? o.schema_name;
  return html`<b class="jmono" title=${o.schema_ref || o.schema_name}>${shown}</b>`;
}

/** What kind of file it must be, in words. */
export function formatOf(o: ContractSpec): unknown {
  const tip = o.schema_ref || o.schema_name;
  if (o.schema_name === 'text') return msg('text file');
  const root = rootOf(o.schema_name);
  if (root === 'str') return html`<span title=${tip}>${msg('text (JSON string)')}</span>`;
  if (root) return html`<span title=${tip}>${msg(str`JSON value of type ${root}`)}</span>`;
  return msg(html`JSON object, schema ${schemaName(o)}`);
}

/** The checks beyond the schema (validators), each with its result when the status tells it; null when there are none. */
export function otherChecks(o: ContractSpec): TemplateResult | null {
  const names = o.validators ?? [];
  if (!names.length) return null;
  const errors = (o.errors ?? []).join('\n');
  const mark = (n: string) =>
    o.status === 'valid' ? fieldMark(true, msg('passed')) : errors.includes(n) ? fieldMark(false, msg('failed checks')) : nothing;
  return html`${names.map((n, i) => html`${i ? ', ' : ''}<span class="jmono">${n}</span> ${mark(n)}`)}`;
}

/** Who writes a file, for naming the task an input should have come from. */
export interface Producer {
  /** "kind · unit" of the task that writes it. */
  name: string;
  /** The file exists now. */
  written: boolean;
  /** What happened to that task, when known. */
  outcome?: Outcome | undefined;
}

/**
 * Why a task never ran, in one line beside its status: the input it was refused
 * for (from its check errors) and, when known, the task that should have written it.
 */
export function notRunText(o: ContractSpec, run: string, producerOf?: (path: string) => Producer | undefined): string {
  const errors = o.errors ?? [];
  const p = inputProblems(`invalid input: ${errors.map((e) => e.replace(/^invalid input:\s*/, '')).join('; ')}`)[0];
  if (!p) return errors[0] ? sentence(runRelative(errors[0], run)) : msg('An input was missing or failed checks');
  const from = producerOf?.(p.path);
  return sentence(inputCause(runRelative(p.path, run), p.problem, from));
}

/**
 * What a contract file must be, as labelled lines a reader can follow without
 * knowing the contract machinery: its format, and (for an output) whether a file
 * from before the task counts, or (for an input) when it is checked and whether
 * the task can start without it.
 */
export function fileConditions(o: ContractSpec, role: 'input' | 'output'): TemplateResult {
  const format = formatOf(o);
  const checks = otherChecks(o);
  const rows: [string, unknown, string?][] =
    role === 'output'
      ? [
          [msg('Format'), format],
          ...(checks ? [[msg('Other checks'), checks, msg('Checks beyond the schema (validators)')] as [string, unknown, string]] : []),
          [msg('Must be written during the task'), o.fresh ? msg('yes') : msg('no'), o.fresh ? msg('A file from before the task does not count') : msg('A file from before the task counts')],
        ]
      : [
          [msg('Format'), format],
          ...(checks ? [[msg('Other checks'), checks, msg('Checks beyond the schema (validators)')] as [string, unknown, string]] : []),
          [msg('Check time'), msg('when the task starts')],
          [msg('Required'), o.required ? msg('yes') : msg('no')],
        ];
  return html`<dl class="conds">
    ${rows.map(([k, v, tip]) => html`<dt>${k}</dt><dd title=${tip ?? ''}>${v}</dd>`)}
  </dl>`;
}

/**
 * One contract file of a task, as a card: status, path, what it must be, the
 * field check, the check errors. A task that never ran gets one line saying
 * why; a task that failed without writing the file gets its status and path
 * only (the status names the cause).
 */
export function ioFileCard(
  o: ContractSpec,
  role: 'input' | 'output',
  run = '',
  opts: {
    producerOf?: (path: string) => Producer | undefined;
    /** Where the file comes from, as a line under its path ("Output of prepare · zeta"). */
    origin?: unknown;
    /** In place of the status chip: an input written by an earlier task shows that task's check of it. */
    chip?: TemplateResult;
  } = {},
): TemplateResult {
  const stat =
    role === 'output'
      ? html`<span class="ct-chip ${o.status ?? ''}" title=${o.status ? contractStatusWhy(o.status) : ''}>${o.status ? contractStatusLabel(o.status) : '—'}</span>${(o.rounds ?? 0) > 1
            ? html` <span class="meta" title=${correctionTip()}>${correctionsLabel(o.rounds, o.status === 'valid')}</span>`
            : nothing}`
      : inputChip(o);
  const head = html`<div class="io-hd">${opts.chip ?? stat}<span class="jmono ct-path" title=${o.path}>${runRelative(o.path, run)}</span></div>${opts.origin
    ? html`<div class="meta io-from">${opts.origin}</div>`
    : nothing}`;
  if (role === 'output' && o.status === 'refused') {
    return html`<div class="io-card one">${head}<div class="meta">${notRunText(o, run, opts.producerOf)}</div></div>`;
  }
  if (role === 'output' && o.status === 'failed' && !o.file.exists) {
    return html`<div class="io-card one">${head}</div>`;
  }
  const errors = o.errors ?? [];
  return html`<div class="io-card">
    ${head}
    ${fileConditions(o, role)}
    ${fieldCheckTable(o)}
    ${errors.length ? html`<h4>${msg('Errors')}</h4><pre class="ct-err">${errors.map((e) => runRelative(e, run)).join('\n')}</pre>` : nothing}
  </div>`;
}

export const contractStyles = css`
  .ct-lead { margin: 2px 0 8px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 6px; }
  .conds { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; margin: 2px 0 10px; font-size: 12px; }
  .conds dt { color: var(--text-muted); }
  .conds dd { margin: 0; color: var(--text-2); }
  /* sized to its content, so the check mark sits next to the value it judges; a long value wraps */
  .ct-check { width: auto; max-width: 100%; border-collapse: collapse; }
  .ct-check th { text-align: left; font-size: 11.5px; color: var(--text-muted);
    font-weight: 600; padding: 4px 20px 4px 0; border-bottom: 1px solid var(--line); }
  .ct-check td { padding: 5px 20px 5px 0; border: 0; border-bottom: 1px solid var(--line); vertical-align: baseline; font-size: 12.5px; }
  .ct-check th:last-child, .ct-check td:last-child { padding-right: 0; }
  .ct-check td:nth-child(3) { overflow-wrap: anywhere; }
  .ct-check tr:last-child td { border-bottom: 0; }
  .ct-check td:first-child { white-space: nowrap; font-weight: 600; }
  .ct-check td:last-child { white-space: nowrap; }
  .ct-check i { font-style: normal; color: var(--text-muted); font-size: 11px; margin-left: 4px; }
  .fk { font-size: 12px; }
  .fk.ok { color: var(--text-2); }
  .fk.ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .fk.bad { color: var(--status-failed); font-weight: 600; }
  .fk.warn { color: var(--status-attention); }
  .fk.none { color: var(--text-muted); }
  .js { color: var(--code-string); }
  .jn { color: var(--code-number); }
  .note { margin-top: 6px; }
  .ct-raw { margin-top: 8px; }
  .ct-raw > summary { cursor: pointer; color: var(--text-muted); font-size: 12px; }
  .ct-err { color: var(--status-failed); white-space: pre-wrap; }
  .ct-fields { border-collapse: collapse; width: 100%; }
  .ct-fields td { padding: 2px 10px 2px 0; border: 0; font-size: 12px; }
  .ct-in { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-top: 1px solid var(--line); }
  h4 { margin: 8px 0 6px; font-size: 12px; color: var(--text-2); font-weight: 600; }
  .io-card { border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; background: var(--raise); }
  .io-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  .io-from { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; margin: -2px 0 8px; }
  .io-hd .ct-path { flex: 1; }
  .io-card.one .io-hd { margin-bottom: 2px; }
`;
