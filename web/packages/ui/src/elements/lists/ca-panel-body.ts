import { typedBody, type CodeBody, type PanelBody, type TableBody, type TreeBody, type TreeLink, type TypedPanelBody } from '@contraagent/api';
import '@contraagent/elements/charts/define';
import '@contraagent/elements/code/define';
import '@contraagent/elements/data-table/define';
import '@contraagent/elements/json-tree/define';
import '@contraagent/elements/tiles/define';
import '@contraagent/elements/tree/define';
import { sortRows, type SortState } from '@contraagent/elements/data-table';
import { md } from '@contraagent/elements/markdown';
import { base, meterStyles, prose } from '@contraagent/elements/styles';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { bodyColumns, bodyTiles, bodyTree, rowTone, type BodyRow } from '../../adapters/panel-body.js';
import { emit } from '../../core/events.js';
import { chartStrings, codeStrings, numberText, treeStrings } from '../../words/panels.js';
import { tableStrings } from '../../words/table.js';

/** The look of a table body's cells, inside `<cae-data-table>`. */
const CELLS = [
  meterStyles,
  css`
    caption { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    /* a narrow screen scrolls the table sideways rather than cutting every cell */
    tr { column-gap: 12px; padding: 6px 12px; border-bottom: 1px solid var(--line); font-size: 12px; min-width: 560px; }
    th, td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    thead tr { color: var(--text-muted); font-size: 11px; }
    tbody [data-align='end'] { font-variant-numeric: tabular-nums; }
    tbody tr[data-tone='failed'], tbody tr[data-tone='attention'] { box-shadow: inset 2px 0 0 var(--tone); }
    td a, th a { color: var(--accent); text-decoration: none; }
    td a:hover, th a:hover, td a:focus-visible, th a:focus-visible { text-decoration: underline; }
  `,
];

/**
 * A pipeline's own view drawn from its typed body (`PanelBody`): tiles, a table, charts,
 * a status grid, notes, code, trees, and blocks of them one under another, each under its title
 * (folded when the body says `collapsed`). A tree whose nodes hold code shows the selected
 * node's code beside it; a node with a link leads to a body of the panel (its `anchor`), a
 * run panel's tab or a task. A body of another shape, inside blocks, is shown as a JSON tree.
 *
 * @fires ca-navigate - a tree node's link to a run panel's tab or a task was chosen
 */
@customElement('ca-panel-body')
@localized()
export class CaPanelBody extends LitElement {
  static override styles = [
    base,
    prose,
    css`
      :host { display: block; }
      /* a note reads as text beside the figures; a tone puts a rule beside it, the words say why */
      .note { font-size: var(--font-size-sm); color: var(--text-2); line-height: 1.55; max-width: 78ch; }
      .note > :first-child { margin-top: 0; }
      .note > :last-child { margin-bottom: 0; }
      .note[data-tone] { padding-left: 10px; border-left: 3px solid var(--line2); }
      .note[data-tone='failed'] { border-left-color: var(--status-failed); }
      .note[data-tone='attention'] { border-left-color: var(--status-attention); }
      .note[data-tone='done'] { border-left-color: var(--status-done); }
      .note[data-tone='running'] { border-left-color: var(--status-running); }
      .block + .block { margin-top: 18px; }
      h4 { margin: 0 0 8px; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-2); }
      details > summary { cursor: pointer; margin-bottom: 8px; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-2); }
      details:not([open]) > summary { margin-bottom: 0; }
      .block[data-anchor] { scroll-margin-top: 12px; }
      .block[data-anchor]:focus { outline: none; }
      /* a tree beside the code of its selected node; one under the other on a narrow screen */
      .pair { display: grid; grid-template-columns: minmax(180px, 30%) minmax(0, 1fr); gap: 12px; align-items: start; }
      .pair > .tree { border: 1px solid var(--line); border-radius: var(--radius-md); max-height: 70vh; overflow: auto; }
      .pane { min-width: 0; }
      @media (max-width: 720px) { .pair { grid-template-columns: minmax(0, 1fr); } .pair > .tree { max-height: 40vh; } }
    `,
  ];

  @property({ attribute: false }) body: PanelBody | undefined;

  /** The order of each table's rows, by the table's place in the body. */
  @state() private sorts = new Map<string, SortState>();
  /** The node the reader selected in each tree, by the tree's place in the body. */
  @state() private picks = new Map<string, string>();

  override render() {
    const typed = typedBody(this.body);
    return typed ? this.draw(typed, '0') : html`<cae-json-tree .value=${this.body ?? {}}></cae-json-tree>`;
  }

  /** One body, under its title; `at` is its place in the body, which keeps a table's order. */
  private draw(b: TypedPanelBody, at: string): TemplateResult {
    const inner = this.content(b, at);
    const anchor = b.anchor || nothing;
    if (!b.title) return html`<div class="block" data-anchor=${anchor} tabindex=${b.anchor ? -1 : nothing}>${inner}</div>`;
    return b.collapsed
      ? html`<details class="block" data-anchor=${anchor} tabindex=${b.anchor ? -1 : nothing}><summary>${b.title}</summary>${inner}</details>`
      : html`<div class="block" data-anchor=${anchor} tabindex=${b.anchor ? -1 : nothing}><h4>${b.title}</h4>${inner}</div>`;
  }

  private code(c: CodeBody, path?: string): TemplateResult {
    return html`<cae-code .code=${c.text} .language=${c.language ?? ''} .start=${c.start ?? 1} .highlight=${c.highlight ?? []}
      .path=${c.path ?? path ?? ''} .label=${c.title ?? c.path ?? path ?? ''} ?wrap=${!!c.wrap} .strings=${codeStrings()}></cae-code>`;
  }

  /** A tree, and the selected node's code beside it: the texts come with the body, so a selection sends no request. */
  private tree(b: TreeBody, at: string): TemplateResult {
    const { items, nodes, first } = bodyTree(b);
    const picked = this.picks.get(at);
    const selected = picked !== undefined && nodes.has(picked) ? picked : first;
    const node = selected ? nodes.get(selected) : undefined;
    const paired = [...nodes.values()].some((n) => n.code);
    const tree = html`<cae-tree class="tree" .items=${items} .selected=${node?.code ? selected : null} .label=${b.title ?? ''}
      .strings=${treeStrings()} @cae-select=${(e: CustomEvent<{ id: string | null }>) => this.choose(at, e.detail.id, nodes)}></cae-tree>`;
    if (!paired) return tree;
    return html`<div class="pair">
      ${tree}
      <div class="pane">${node?.code ? this.code(node.code, selected ?? '') : html`<div class="meta">${msg('No selection')}</div>`}</div>
    </div>`;
  }

  private choose(at: string, id: string | null, nodes: ReadonlyMap<string, { code?: CodeBody | null; link?: TreeLink | null }>): void {
    const node = id === null ? undefined : nodes.get(id);
    if (!node || id === null) return;
    if (node.code) this.picks = new Map(this.picks).set(at, id);
    else if (node.link) this.follow(node.link);
  }

  /** Goes where a node leads: a body of this panel, a run panel's tab or a task, in its run or the one shown. */
  private follow(link: TreeLink): void {
    if (link.anchor) {
      const to = this.renderRoot.querySelector<HTMLElement>(`[data-anchor="${CSS.escape(link.anchor)}"]`);
      to?.scrollIntoView?.({ block: 'start' });
      to?.focus({ preventScroll: true });
      return;
    }
    const run = link.run ? { run: link.run } : {};
    if (link.panel) emit(this, 'ca-navigate', { page: '', ...run, tab: `panel:${link.panel}` });
    else if (link.task) emit(this, 'ca-navigate', { page: '', ...run, tab: 'stream', key: link.task, view: 'transcript', round: null });
  }

  private content(b: TypedPanelBody, at: string): TemplateResult {
    const s = chartStrings();
    switch (b.type) {
      case 'blocks':
        return html`${(b).blocks.map((x, i) => {
          const t = typedBody(x);
          return t ? this.draw(t, `${at}.${i}`) : html`<div class="block"><cae-json-tree .value=${x}></cae-json-tree></div>`;
        })}`;
      case 'tiles':
        return html`<cae-stat-tiles .tiles=${bodyTiles(b.tiles)} .bump=${false}></cae-stat-tiles>`;
      case 'table':
        return this.table(b, at);
      case 'columns':
        return html`<cae-column-chart .label=${b.title ?? ''} .x=${b.x} .series=${b.series} ?stacked=${!!b.stacked}
          .format=${numberText(b.unit)} .strings=${s}></cae-column-chart>`;
      case 'lines':
        return html`<cae-line-chart .label=${b.title ?? ''} .x=${b.x} .series=${b.series} .format=${numberText(b.unit)} .strings=${s}></cae-line-chart>`;
      case 'heatmap':
        return html`<cae-heatmap .label=${b.title ?? ''} .x=${b.x} .y=${b.y} .values=${b.values} .format=${numberText(b.unit)} .strings=${s}></cae-heatmap>`;
      case 'hbars':
        return html`<cae-bar-chart .label=${b.title ?? ''} .bars=${b.bars.map((x) => ({ label: x.label, value: x.value, tone: x.tone ?? undefined }))}
          .format=${numberText(b.unit)} .strings=${s}></cae-bar-chart>`;
      case 'status_grid':
        return html`<cae-state-grid .label=${b.title ?? ''} .x=${b.x} .y=${b.y} .cells=${b.cells} .strings=${s}></cae-state-grid>`;
      case 'note':
        // Escaped markdown: any markup the text holds is shown as text; links keep only http(s).
        return html`<div class="note" data-tone=${b.tone && b.tone !== 'neutral' ? b.tone : nothing}>${unsafeHTML(md(b.text))}</div>`;
      case 'code':
        return this.code(b);
      case 'tree':
        return this.tree(b, at);
      default:
        return html`${nothing}`;
    }
  }

  private table(b: TableBody, at: string): TemplateResult {
    const columns = bodyColumns(b);
    const rows = b.rows as BodyRow[];
    const keys = new Map(rows.map((r, i) => [r, String(i)]));
    const sort = this.sorts.get(at) ?? null;
    const shown = sort ? sortRows(rows, columns, sort) : rows;
    return html`<cae-data-table
      .columns=${columns}
      .rows=${shown}
      .rowKey=${(r: BodyRow) => keys.get(r) ?? ''}
      .rowTone=${rowTone}
      .activatable=${false}
      .sort=${sort}
      .cellStyles=${CELLS}
      .caption=${b.title ?? ''}
      .strings=${tableStrings(msg('No rows'))}
      @cae-sort=${(e: CustomEvent<SortState>) => (this.sorts = new Map(this.sorts).set(at, e.detail))}
    ></cae-data-table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-panel-body': CaPanelBody;
  }
}
