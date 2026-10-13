import type { DefinitionFile, TaskDefinition } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { highlight, mdFile } from '@contraagent/elements/markdown';
import { instructionsHtml, markInstructions } from '../../words/prompt.js';
import { RememberedSet } from '../../core/memory.js';
import { base, factStyles, prose } from '@contraagent/elements/styles';
import { contractChipStyles } from './contract-parts.js';

const OPEN_FIRST = new Set(['instructions', 'schema', 'agent']);

/** A long path cut from the left to its last two parts (`…/plugins/docs`); the full path goes in a tooltip. */
const tail = (p: string): string => {
  const parts = p.split('/').filter(Boolean);
  return parts.length > 2 ? `…/${parts.slice(-2).join('/')}` : p;
};

interface DeclaredContract {
  io: string;
  path: string;
  schema: string;
}

/**
 * What defines one kind of task: its role, plugin, params and output, the
 * contracts it declares, and every file (instructions, the role's agent file,
 * skills, the schema), markdown rendered with a switch to the source.
 */
@customElement('ca-definition')
@localized()
export class CaDefinition extends LitElement {
  static override styles = [
    base,
    prose,
    factStyles,
    contractChipStyles,
    css`
      :host { display: block; }
      .ct-in { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-top: 1px solid var(--line); }
      .df { border-top: 1px solid var(--line); }
      /* A file: its name opens and closes it (a disclosure button), and a Markdown file has its own toggle beside it. */
      .df-hd { padding: 6px 2px; display: flex; gap: 10px; align-items: center; }
      .df-sum { flex: 1 1 auto; min-width: 0; display: flex; gap: 10px; align-items: center; padding: 0; background: none; border: 0;
        color: inherit; text-align: start; cursor: pointer; }
      .df-sum::before { content: '▸'; color: var(--text-muted); width: 10px; flex: none; transition: transform 0.15s; }
      .df-sum[aria-expanded='true']::before { transform: rotate(90deg); }
      .py-sig { font-family: var(--mono); font-size: 14px; padding: 10px 14px; background: var(--well); border: 1px solid var(--line);
        border-radius: 8px; overflow-x: auto; white-space: pre; }
      .py-where { margin: 6px 2px 12px; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); overflow-wrap: anywhere; }
      .py-doc { margin: 0 0 12px; padding: 8px 12px; border-left: 3px solid var(--line2); color: var(--text-2); white-space: pre-wrap; line-height: 1.6; }
      .src { display: grid; grid-template-columns: auto minmax(0, 1fr); background: var(--well); border: 1px solid var(--line);
        border-radius: 8px; font-family: var(--mono); font-size: 12px; line-height: 1.55; max-height: 520px; overflow: auto; }
      .src pre { margin: 0; padding: 10px 12px; white-space: pre; }
      .src .ln { color: var(--text-muted); text-align: right; user-select: none; border-right: 1px solid var(--line); opacity: 0.7; }
    `,
  ];

  @property({ attribute: false }) definition: TaskDefinition | null = null;
  /** Remember open files and the rendered/source choice under this id (in the history entry, or the embedded monitor's memory). */
  @property() memory = 'definition';

  private open = new RememberedSet('definition:open', this);
  private source = new RememberedSet('definition:source', this);

  override willUpdate(changed: Map<string, unknown>): void {
    if (changed.has('memory')) {
      this.open = new RememberedSet(`${this.memory}:open`, this);
      this.source = new RememberedSet(`${this.memory}:source`, this);
    }
  }

  override render() {
    const def = this.definition;
    if (!def) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${msg('No definition')}</b></div>`;
    }
    if (def.executor === 'python') return this.python(def);
    const dirs = def.plugin_dirs || [];
    const facts: [string, string | TemplateResult][] = [
      [msg('Role'), def.role || msg('none', { id: 'none', desc: 'An empty value' })],
      [
        dirs.length > 1 ? msg('Plugin directories') : msg('Plugin directory'),
        dirs.length ? html`${dirs.map((d, i) => html`${i ? ', ' : ''}<span class="jmono" title=${d}>${tail(d)}</span>`)}` : msg('none', { id: 'none', desc: 'An empty value' }),
      ],
      [msg('Parameters'), def.params || msg('none', { id: 'none', desc: 'An empty value' })],
      [msg('Output', { id: 'definition-output', desc: 'The output file of a task definition' }), def.output || msg('none', { id: 'none', desc: 'An empty value' })],
      ...((def.validators || []).length ? [[msg('Other checks'), (def.validators || []).join(', ')] as [string, string]] : []),
    ];
    const declared = Array.isArray(def['declared']) ? (def['declared'] as DeclaredContract[]) : [];
    // The role file this kind runs as goes first, open; other roles' files are folded.
    const isRole = (f: DefinitionFile) => f.part === 'agent' && !!def.role && f.path.replace(/^.*\//, '') === `${def.role}.md`;
    const files = [...(def.files || [])].sort((a, b) => Number(isRole(b)) - Number(isRole(a)));
    return html`<div class="drv-facts" style="margin-bottom:10px">${facts.map(([k, v]) => html`<span><i>${k}</i>${v}</span>`)}</div>
      ${declared.length
        ? html`<h4 class="sect-h">${msg('Checked files')}</h4>
            ${declared.map(
              (x) => html`<div class="ct-in">
                <span class="ct-chip">${x.io}</span><span class="jmono">${x.path}</span>
                <span class="meta" title=${msg('The schema the file is checked against')}>${msg(str`Schema ${x.schema}`)}</span>
              </div>`,
            )}`
        : nothing}
      ${files.length
        ? html`<h4 class="sect-h">${msg('Files')}</h4>${files.map((f) => this.file(f, isRole(f), !!def.role))}`
        : html`<div class="meta">${msg(html`No files | defined in Python code (<code>TaskAdapter</code>)`)}</div>`}`;
  }

  /** A Python task's kind, shown as its function: signature, where it is, docstring, facts, source. */
  private python(def: TaskDefinition) {
    const src = (def.files || []).find((f) => f.part === 'source');
    const first = def.line ?? 1;
    const lines = src ? src.text.replace(/\n$/, '').split('\n').length : 0;
    const facts: [string, string][] = [
      [msg('Parameters'), def.params && def.params !== 'none' ? def.params : msg('none', { id: 'none', desc: 'An empty value' })],
      [msg('Output', { id: 'definition-output', desc: 'The output file of a task definition' }), def.output && def.output !== 'none' ? def.output : msg('none', { id: 'none', desc: 'An empty value' })],
      ...((def.validators || []).length ? [[msg('Other checks'), (def.validators || []).join(', ')] as [string, string]] : []),
    ];
    return html`${def.signature
        ? html`<div class="py-sig hl">${unsafeHTML(highlight(`def ${def.signature}`, 'python'))}</div>`
        : nothing}
      <div class="py-where">
        ${def.function ?? def.kind}${def.file
          ? html` | <span title=${def.file}>${def.file.replace(/^.*\//, '')}${def.line ? `:${def.line}` : ''}</span>`
          : nothing}
      </div>
      ${def.doc ? html`<div class="py-doc">${def.doc}</div>` : nothing}
      <div class="drv-facts" style="margin-bottom:12px">${facts.map(([k, v]) => html`<span><i>${k}</i>${v}</span>`)}</div>
      ${src
        ? html`<h4 class="sect-h">${msg('Source')}</h4>
            <div class="src">
              <pre class="ln">${Array.from({ length: lines }, (_, i) => first + i).join('\n')}</pre>
              <pre class="hl">${unsafeHTML(highlight(src.text.replace(/\n$/, ''), 'python'))}</pre>
            </div>`
        : nothing}`;
  }

  private file(f: DefinitionFile, isRole = false, hasRole = false) {
    const id = `${f.part}|${f.path}`;
    const isMd = /\.md$/i.test(f.path);
    const instructions = f.part === 'instructions';
    const showSource = !isMd || this.source.has(id);
    // Of the role files, only the one this kind uses opens by default.
    const openFirst = f.part === 'agent' && hasRole ? isRole : OPEN_FIRST.has(f.part);
    const isOpen = this.open.has(id) || (openFirst && !this.open.has(`closed:${id}`));
    const toggle = () => {
      this.open.set(id, !isOpen);
      this.open.set(`closed:${id}`, isOpen);
      this.requestUpdate();
    };
    const flip = () => {
      this.source.set(id, !this.source.has(id));
      this.requestUpdate();
    };
    return html`<div class="df">
      <div class="df-hd">
        <button type="button" class="df-sum" aria-expanded=${isOpen ? 'true' : 'false'} @click=${toggle}>
          <span class="tag">${f.part}</span><span class="jmono">${f.path}</span>
          ${isRole ? html`<span class="ct-chip">${msg('Role of this kind')}</span>` : nothing}
        </button>
        ${isMd
          ? html`<button type="button" class="df-tog" @click=${flip}>${showSource ? msg('Show rendered') : msg('Show source')}</button>`
          : nothing}
      </div>
      ${!isOpen
        ? nothing
        : showSource
          ? html`<pre class="df-text"><code class="hl">${unsafeHTML(instructions ? instructionsHtml(f.text) : highlight(f.text, f.path))}</code></pre>`
          : unsafeHTML(mdFile(f.text, instructions ? markInstructions : undefined))}
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-definition': CaDefinition;
  }
}
