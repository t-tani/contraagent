import { LitElement, html, nothing, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { withDefaults } from '../core/strings.js';
import { base } from '../styles/index.js';
import { checkTableStyles, verdictStyles } from './styles.js';
import { DEFAULT_CHECK_TABLE_STRINGS, type CheckRow, type CheckTableStrings, type Verdict } from './types.js';

/**
 * A verdict in words (`.verdict`, `data-verdict`; `verdictStyles`): ✓ before a
 * pass, ✕ before a failure, hidden from screen readers, which read the word.
 * Nothing for `none` without a word.
 */
export function verdict(v: Verdict, label: string, tip = ''): TemplateResult | typeof nothing {
  if (v === 'none' && !label) return nothing;
  const mark = v === 'pass' ? '✓' : v === 'fail' ? '✕' : '';
  return html`<span class="verdict" part="verdict" data-verdict=${v} title=${tip || nothing}>${mark
    ? html`<span aria-hidden="true">${mark}</span> `
    : nothing}${label}</span>`;
}

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** A value in a line: a string quoted and cut, a list's length and first items, an object's first keys. */
function shortValue(v: unknown, s: CheckTableStrings): TemplateResult {
  if (v === undefined) return html`<span class="jdim">—</span>`;
  if (typeof v === 'string') return html`<span class="js" title=${v}>"${cut(v, 90)}"</span>`;
  if (Array.isArray(v)) {
    const head = v
      .slice(0, 3)
      .map((x) => (typeof x === 'string' ? `"${cut(x, 28)}"` : JSON.stringify(x)))
      .join(', ');
    return html`<span class="jn">${s.items(v.length)}</span>
      <span class="jdim">${head}${v.length > 3 ? ', …' : ''}</span>`;
  }
  if (v !== null && typeof v === 'object') return html`<span class="jn">${s.object}</span> <span class="jdim">${Object.keys(v).slice(0, 4).join(', ')}</span>`;
  return html`<span class="jn">${JSON.stringify(v)}</span>`;
}

/**
 * Named values checked one by one: a row per name, with what it must be, what
 * it is and the verdict. Without `showValues`, only the names and what each
 * must be (nothing to check them against).
 *
 * @tagname cae-check-table
 * @csspart table - the `<table>`
 * @csspart row - each row of a name
 * @csspart verdict - each verdict
 */
export class CaeCheckTable extends LitElement {
  static override styles = [base, verdictStyles, checkTableStyles];

  @property({ attribute: false }) rows: readonly CheckRow[] = [];
  /** Show the values and the verdicts. */
  @property({ type: Boolean }) showValues = true;
  @property({ attribute: false }) strings: Partial<CheckTableStrings> = {};

  override render() {
    const s = withDefaults(DEFAULT_CHECK_TABLE_STRINGS, this.strings);
    const all = this.showValues;
    return html`<table part="table">
      <thead><tr>
        <th scope="col">${s.name}</th><th scope="col">${s.expected}</th>
        ${all ? html`<th scope="col">${s.actual}</th><th scope="col">${s.verdict}</th>` : nothing}
      </tr></thead>
      <tbody>
        ${this.rows.map(
          (r) => html`<tr part="row">
            <td class="jmono">${r.name}</td>
            <td class=${r.extra ? 'jdim' : 'jmono jdim'}>${r.expected}${r.optional ? html` <i>${s.optional}</i>` : nothing}</td>
            ${all
              ? html`<td class="value">${shortValue(r.hasValue ? r.value : undefined, s)}</td>
                  <td>${verdict(r.verdict, r.verdictLabel, r.tip)}</td>`
              : nothing}
          </tr>`,
        )}
      </tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-check-table': CaeCheckTable;
  }
}
