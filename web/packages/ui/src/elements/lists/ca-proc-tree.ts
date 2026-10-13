import type { ProcNode, Procs } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { starts } from '@contraagent/elements';
import { kindUnit } from '../../words/format.js';
import { base } from '@contraagent/elements/styles';
import '@contraagent/elements/count/define';

/** The run's live process tree (its first root): pid, command, and how long each has run. */
@customElement('ca-proc-tree')
@localized()
export class CaProcTree extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .ptree2 { font-family: var(--mono); font-size: 11.5px; max-height: 220px; overflow: auto; }
      .pt-n { display: flex; gap: 10px; align-items: center; padding: 3px 6px 3px calc(6px + var(--d) * 18px); border-radius: 6px; position: relative; }
      .pt-n:hover { background: color-mix(in srgb, var(--text) 4%, transparent); }
      .pt-n::before { content: ''; position: absolute; left: calc(var(--d) * 18px - 8px); top: 0; bottom: 50%; width: 8px;
        border-left: 1px solid var(--line2); border-bottom: 1px solid var(--line2); }
      .pt-n.root::before { display: none; }
      .pt-pid { color: var(--text-muted); min-width: 58px; }
      .pt-cmd { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; color: var(--text-2); }
      .pt-n.llm .pt-cmd { color: var(--text); }
      .pt-n.llm .pt-pid { box-shadow: inset 2px 0 0 color-mix(in srgb, var(--agent) 70%, transparent); padding-left: 6px; }
      .pt-age { color: var(--text-muted); }
    `,
  ];

  @property({ attribute: false }) procs: Procs | null = null;

  override render() {
    const root = this.procs?.tree[0];
    if (!root) return html`<div class="meta">${msg('No running processes')}</div>`;
    return html`<div class="ptree2">${this.node(root, 0)}</div>`;
  }

  private node(n: ProcNode, d: number): TemplateResult {
    const cmd = n.full_cmd || n.cmd || '';
    const label = (n.cmd || cmd).split(' ').slice(0, 3).join(' ');
    const llm = /\b(claude|omp)\b/.test(cmd);
    return html`<div class="pt-n ${llm ? 'llm' : ''} ${d ? '' : 'root'}" style="--d:${d}" title=${cmd}>
        <span class="pt-pid">${n.pid}</span>
        <span class="pt-cmd">${n.key ? html`<b>${kindUnit(n)}</b> ` : nothing}${label.length > 70 ? `${label.slice(0, 70)}…` : label}</span>
        <cae-elapsed class="pt-age" .since=${starts.at(`p:${n.pid}`, n.age_s)}></cae-elapsed>
      </div>
      ${(n.children ?? []).map((c) => this.node(c, d + 1))}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-proc-tree': CaProcTree;
  }
}
