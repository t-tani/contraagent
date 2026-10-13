// A task's contract file as a card, for a task's input and output panes. Its
// classes are in `contractStyles`.
import { runRelative, type ContractSpec } from '@contraagent/api';
import { msg } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { correctionTip, correctionsLabel, notRunText, type Producer } from '../../words/contract.js';
import { contractChip, fieldCheckTable, fileConditions, inputChip } from './contract-parts.js';

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
      ? html`${contractChip(o.status)}${(o.rounds ?? 0) > 1
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
