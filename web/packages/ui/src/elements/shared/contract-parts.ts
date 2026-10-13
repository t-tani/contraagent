// A contract file read the way a person checks it: each field of its schema
// against what the file holds. Templates shared by the outputs view and a task's
// input/output view (`file-card.ts`); their classes are in `contractStyles`.
import { type ContractSpec, type ContractStatus, type FileView } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { css, html, nothing, type TemplateResult } from 'lit';
import { facts, localTime } from '../../words/format.js';
import { contractStatusLabel, contractStatusWhy } from '../../words/contract.js';
import { statusChip } from '@contraagent/elements/primitives';
import { verdict, verdictStyles } from '@contraagent/elements/check-table';
import '@contraagent/elements/check-table/define';
import { checkRowsFromContract, checkTableStrings, contentObject, rootOf } from '../../adapters/check-rows.js';
import { contractTone } from '../../lib/tone.js';
import '@contraagent/elements/json-tree/define';

/** An input file's state: found, or missing (and whether the task needed it). */
export function inputChip(o: ContractSpec): TemplateResult {
  const ok = !!o.file.exists;
  const text = ok ? msg('found') : o.required ? msg('missing (required)') : msg('missing (optional)');
  return statusChip('ct-chip', { text, tone: ok ? 'done' : o.required ? 'failed' : 'muted' });
}

/** A checked file's status as a chip, with its cause as the tooltip, and a count after the word when given; '—' without one. */
export function contractChip(s: ContractStatus | null | undefined, count?: number): TemplateResult {
  if (!s) return statusChip('ct-chip', { text: '—' });
  return statusChip('ct-chip', {
    text: count === undefined ? contractStatusLabel(s) : html`${contractStatusLabel(s)} <b>${count}</b>`,
    tone: contractTone(s),
    title: contractStatusWhy(s),
  });
}


/** The file's content as a tree, or as text when it is not JSON. */
export function fileContent(f: FileView): TemplateResult {
  const c = f.content;
  return c !== null && typeof c === 'object'
    ? html`<cae-json-tree .value=${c}></cae-json-tree>`
    : html`<pre class="jtree">${typeof c === 'string' ? c : msg('Not JSON')}</pre>`;
}

/**
 * The contract on the left of each row, the file's value on the right, a
 * verdict per field (`<cae-check-table>`); a text result shows the file itself.
 */
export function fieldCheckTable(o: ContractSpec): TemplateResult {
  const f = o.file;
  const rows = checkRowsFromContract(o);
  const whole = html`<details class="ct-raw">
    <summary>${wholeFile(f)}</summary>
    ${fileContent(f)}
  </details>`;
  // A text result (a text file, or one JSON value) has no fields to check: show the file itself.
  if (!rows) return f.exists ? whole : html``;
  // No file: the fields it must have, and nothing to check them against; its status chip says it is not there.
  if (!f.exists) return rows.length ? html`<cae-check-table .rows=${rows} .showValues=${false} .strings=${checkTableStrings()}></cae-check-table>` : html``;
  return html`<cae-check-table .rows=${rows} .strings=${checkTableStrings()}></cae-check-table>
    ${!contentObject(o) ? html`<div class="meta note">${msg('Not a JSON object')}</div>` : nothing}
    ${whole}`;
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
    o.status === 'valid' ? verdict('pass', msg('passed')) : errors.includes(n) ? verdict('fail', msg('failed checks')) : nothing;
  return html`${names.map((n, i) => html`${i ? ', ' : ''}<span class="jmono">${n}</span> ${mark(n)}`)}`;
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

/** A chip that names a checked file's status (`statusChip`), or a neutral label in its shape. */
export const contractChipStyles = css`
  .ct-chip { display: inline-block; padding: 1px 10px; border-radius: var(--radius-pill); font-size: 11.5px; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .ct-chip b { margin-left: 4px; }
  /* a checked file's status: tinted by its tone, passed quiet with its ✓ in an outline */
  .ct-chip[data-tone] { background: var(--tone-bg); color: var(--tone); }
  .ct-chip[data-tone='done'] { background: none; box-shadow: inset 0 0 0 1px var(--line2); color: var(--text-2); }
`;

export const contractStyles = css`
  ${contractChipStyles}
  ${verdictStyles}
  .ct-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ct-lead { margin: 2px 0 8px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 6px; }
  .conds { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; margin: 2px 0 10px; font-size: 12px; }
  .conds dt { color: var(--text-muted); }
  .conds dd { margin: 0; color: var(--text-2); }
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
