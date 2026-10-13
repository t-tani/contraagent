import { LitElement, html, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { base, prose } from '../styles/index.js';

const isLeaf = (x: unknown): boolean =>
  x === null || typeof x !== 'object' || (Array.isArray(x) ? !x.length : !Object.keys(x).length);

/**
 * Any JSON value as a foldable tree: the first level open, deeper levels folded.
 *
 * @tagname cae-json-tree
 * @csspart tree - the tree
 */
export class CaeJsonTree extends LitElement {
  static override styles = [base, prose];

  @property({ attribute: false }) value: unknown;
  /** Levels opened from the start. */
  @property({ type: Number }) open = 1;

  override render() {
    return html`<div class="jtree" part="tree">${this.node(this.value, 0)}</div>`;
  }

  private node(v: unknown, depth: number): TemplateResult | string {
    if (v === null || typeof v !== 'object') {
      return html`<span class=${typeof v === 'string' ? 'js' : 'jn'}>${JSON.stringify(v) ?? 'undefined'}</span>`;
    }
    const entries: [string | number, unknown][] = Array.isArray(v) ? v.map((x, i) => [i, x]) : Object.entries(v);
    if (!entries.length) return Array.isArray(v) ? '[]' : '{}';
    return html`${entries.map(([k, x]) =>
      isLeaf(x)
        ? html`<div class="jt"><span class="jk">${k}</span>: ${this.node(x, depth + 1)}</div>`
        : html`<details class="jt" ?open=${depth < this.open}>
            <summary>
              <span class="jk">${k}</span>
              <span class="meta">${Array.isArray(x) ? `[${x.length}]` : `{${Object.keys(x as object).length}}`}</span>
            </summary>
            ${this.node(x, depth + 1)}
          </details>`,
    )}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-json-tree': CaeJsonTree;
  }
}
