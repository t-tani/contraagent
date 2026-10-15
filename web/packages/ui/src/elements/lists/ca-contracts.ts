import { deriveRun, isPython, runRelative, type ContractRecord, type ContractSpec, type ContractStatus, type JournalRow, type Outputs, type Plan, type TaskOutcome } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../core/events.js';
import { RememberedSet } from '../../core/memory.js';
import type { TaskView } from '../../core/view-route.js';
import { base } from '@contraagent/elements/styles';
import { executorIcon, executorIconStyles } from '../../words/executor.js';
import { kindUnit } from '../../words/format.js';
import { correctionTip, correctionsLabel, notRunText, type Producer } from '../../words/contract.js';
import { contractChip, contractStyles, fieldCheckTable, fileConditions, inputChip } from '../shared/contract-parts.js';

const CT_ORDER: readonly ContractStatus[] = ['invalid', 'refused', 'failed', 'running', 'pending', 'valid'];

/** Output contracts per status, worst first; a line of text when none is declared. */
export function ctChips(outputs: Outputs | null) {
  const t = outputs?.tally;
  const chips = t ? CT_ORDER.filter((k) => t[k]) : [];
  return chips.length
    ? chips.map((k) => contractChip(k, t?.[k]))
    : html`<span class="meta">${msg('No checked files')}</span>`;
}

const shortPath = (p: string) => p.split('/').slice(-2).join('/');

/** A task as the reader names it: "kind · unit" (a run-scope task: its kind). */
export const taskName = (c: { key: string; kind?: string; unit?: string }): string =>
  kindUnit({ kind: c.kind || c.key, unit: c.unit && c.unit !== c.key ? c.unit : '' });

/** Problems first (the order of `CT_ORDER`), then by task. */
const rank = (s: ContractStatus | null | undefined) => (s ? CT_ORDER.indexOf(s) : CT_ORDER.length);

/**
 * The files each task must write (`OutputContract`) and read (`InputContract`),
 * problems first, each checked field by field against its schema. Links open
 * the task (`ca-open-task`).
 *
 * @fires ca-open-task - `{key, view}`: a link to the task's input, output or transcript
 */
@customElement('ca-contracts')
@localized()
export class CaContracts extends LitElement {
  static override styles = [
    base,
    contractStyles,
    executorIconStyles,
    css`
      :host { display: block; }
      .ct-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      details.ct { border-top: 1px solid var(--line); }
      details.ct > summary { list-style: none; cursor: pointer; padding: 7px 4px; display: flex; align-items: center; gap: 10px; }
      details.ct > summary::-webkit-details-marker { display: none; }
      details.ct > summary::before { content: '▸'; color: var(--text-muted); width: 10px; transition: transform 0.15s; }
      details.ct[open] > summary::before { transform: rotate(90deg); }
      details.ct > summary:hover { background: var(--raise); border-radius: 8px; }
      .k-ic { margin-right: 0; }
      .ct-f { margin-left: auto; white-space: nowrap; }
      .ct-body { padding: 4px 10px 14px 24px; }
      .ct-links { margin-top: 10px; font-size: 12px; }
      .lead { margin: -4px 0 10px; }
      .one { display: flex; align-items: center; gap: 10px; padding: 7px 4px 7px 24px; border-top: 1px solid var(--line); flex-wrap: wrap; }
      .why { color: var(--text-2); font-size: 12px; }
    `,
  ];

  @property({ attribute: false }) outputs: Outputs | null = null;
  /** The run, to show paths inside its directory short. */
  @property() run = '';
  /** The run's journal: a failed task's card shows why it failed. Optional. */
  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The run's plan: with the journal, what happened to the task that writes a missing input. Optional. */
  @property({ attribute: false }) plan: Plan | null = null;
  private outcomes: ReadonlyMap<string, TaskOutcome> = new Map();

  /** Which contracts the reader opened, kept across Back and reload. */
  private readonly open = new RememberedSet('contracts:open', this);

  override render() {
    const cs = this.outputs?.contracts ?? [];
    this.outcomes = this.plan ? deriveRun(this.journal, this.plan).outcomes : new Map<string, TaskOutcome>();
    if (!cs.length) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">▣</span><b>${msg('No checked files')}</b>
        <span>${msg('No task declares an OutputContract or an InputContract')}</span></div>`;
    }
    const outs = cs
      .flatMap((c) => (c.outputs ?? []).map((o) => [c, o] as const))
      .sort(([a, x], [b, y]) => rank(x.status) - rank(y.status) || a.key.localeCompare(b.key));
    const ins = cs.flatMap((c) => (c.inputs ?? []).map((i) => [c, i] as const));
    return html`<div class="g12">
      <section class="panel c12">
        <h3 title=${msg('OutputContract')}>${msg('Outputs')}
          <span class="r">${msg('Files each task must write')}</span></h3>
        <div class="ct-row">${ctChips(this.outputs)}</div>
        ${repeat(outs, ([c, o]) => `out|${c.key}|${o.path}`, ([c, o]) => this.outRow(c, o))}
      </section>
      ${ins.length
        ? html`<section class="panel c12">
            <h3 title=${msg('InputContract')}>${msg('Inputs')}
              <span class="r">${msg('Files each task reads, checked when the task starts')}</span></h3>
            ${repeat(ins, ([c, i]) => `in|${c.key}|${i.path}`, ([c, i]) => this.inRow(c, i))}
          </section>`
        : nothing}
    </div>`;
  }

  private details(id: string, summary: unknown, body: unknown) {
    return html`<details class="ct" ?open=${this.open.has(id)}
      @toggle=${(e: Event) => this.open.set(id, (e.target as HTMLDetailsElement).open)}>
      <summary class="ct-sum">${summary}</summary>
      <div class="ct-body">${body}</div>
    </details>`;
  }

  private link(key: string, view: TaskView, text: string) {
    return html`<a class="lnk" href="#" @click=${(e: Event) => {
      e.preventDefault();
      emit(this, 'ca-open-task', { key, view });
    }}>${text}</a>`;
  }

  private who(c: ContractRecord) {
    const py = isPython(c);
    const kindName = py ? msg('Python task') : msg('Agent task');
    return html`${executorIcon(py, kindName)}
      <b class="jmono" title=${c.key}>${taskName(c)}</b>`;
  }

  /** Who writes each output file: for naming the task a missing input should have come from. */
  private producerOf = (path: string): Producer | undefined => {
    for (const c of this.outputs?.contracts ?? []) {
      const o = (c.outputs ?? []).find((x) => x.path === path);
      if (o) return { name: taskName(c), written: !!o.file.exists, outcome: this.outcomes.get(c.key)?.outcome };
    }
    return undefined;
  };

  /** The reason of a task's last journal row (run-relative), when the journal was given. */
  private reasonOf(key: string): string {
    for (let i = this.journal.length - 1; i >= 0; i--) {
      const r = this.journal[i];
      if (r?.key === key) return runRelative(r.reason, this.run);
    }
    return '';
  }

  private outRow(c: ContractRecord, o: ContractSpec) {
    // A task that never ran: one line saying why, nothing to open.
    if (o.status === 'refused') {
      return html`<div class="one">
        ${contractChip('refused')}${this.who(c)}
        <span class="why">${notRunText(o, this.run, this.producerOf)}</span>
      </div>`;
    }
    const f = o.file;
    const status = o.status;
    const rounds = o.rounds ?? 0;
    const errors = o.errors ?? [];
    const name = taskName(c);
    // The chip says why there is no file; the size column shows a size only when there is one.
    return this.details(
      `out|${c.key}|${o.path}`,
      html`${contractChip(status)}
        ${rounds > 1 ? html`<span class="meta" title=${correctionTip()}>${correctionsLabel(rounds, status === 'valid')}</span>` : nothing}
        ${this.who(c)}
        <span class="jmono jdim ct-path" title=${o.path}>${shortPath(o.path)}</span>
        ${status === 'failed' && this.reasonOf(c.key) ? html`<span class="why">${this.reasonOf(c.key)}</span>` : nothing}
        <span class="meta ct-f">${f.exists ? `${f.size ?? 0} B` : !status ? msg('No file') : nothing}</span>`,
      html`${fileConditions(o, 'output')}
        ${fieldCheckTable(o)}
        ${errors.length ? html`<h4>${msg('Errors')}</h4><pre class="ct-err">${errors.map((e) => runRelative(e, this.run)).join('\n')}</pre>` : nothing}
        <div class="ct-links">
          ${this.link(c.key, 'output', msg(str`${name}: input and output`))}
          ${isPython(c) ? nothing : html`<br />${this.link(c.key, 'transcript', msg(str`${name}: transcript`))}`}
        </div>`,
    );
  }

  private inRow(c: ContractRecord, i: ContractSpec) {
    const f = i.file;
    const ok = !!f.exists;
    return this.details(
      `in|${c.key}|${i.path}`,
      html`${inputChip(i)}
        ${this.who(c)}
        <span class="jmono jdim ct-path" title=${i.path}>${shortPath(i.path)}</span>
        <span class="meta ct-f">${ok ? `${f.size ?? 0} B` : msg('No file')}</span>`,
      html`${fileConditions(i, 'input')}
        ${fieldCheckTable(i)}
        <div class="ct-links">${this.link(c.key, 'input', msg(str`${taskName(c)}: input`))}</div>`,
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-contracts': CaContracts;
  }
}
