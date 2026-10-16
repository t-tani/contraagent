import { LitElement, css, html, nothing, svg, type PropertyValues, type TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { emit } from '../core/events.js';
import { withDefaults } from '../core/strings.js';
import type { Tone } from '../core/tone.js';
import { statusChip } from '../primitives/pill.js';
import { base } from '../styles/index.js';

/** One item of a tree: its name, the items under it, and how it looks. */
export interface TreeItem {
  /** Its id, unique in the tree. */
  id: string;
  name: string;
  /** Its icon: a directory for an item with children, a file for one without, unless given. */
  icon?: 'file' | 'directory' | null;
  /** A word beside the name, coloured by `tone` (with its mark: ✓ done, ✕ failed, ◌ attention). */
  badge?: string | null;
  tone?: Tone | null;
  /** Its children are shown at first (default: true). */
  open?: boolean | null;
  children?: readonly TreeItem[] | null;
  /** A click or Enter selects it (`cae-select`); default: an item with no children. An item with children that is not selectable opens and closes instead. */
  selectable?: boolean | null;
}

export interface TreeStrings {
  /** What a tree with no items shows. */
  empty: string;
}

export const DEFAULT_TREE_STRINGS: Readonly<TreeStrings> = { empty: 'No items' };

/** An item where the tree shows it: its depth (1 at the top), its parent, and its place among its siblings. */
export interface TreeRow {
  item: TreeItem;
  level: number;
  parent: string | null;
  index: number;
  siblings: number;
}

const hasChildren = (t: TreeItem): boolean => !!t.children?.length;
const selectable = (t: TreeItem): boolean => t.selectable ?? !hasChildren(t);

/** The items shown, top to bottom: every item whose ancestors are all open (`isOpen`). */
export function visibleRows(items: readonly TreeItem[], isOpen: (t: TreeItem) => boolean): TreeRow[] {
  const out: TreeRow[] = [];
  const walk = (list: readonly TreeItem[], level: number, parent: string | null) =>
    list.forEach((item, index) => {
      out.push({ item, level, parent, index, siblings: list.length });
      if (hasChildren(item) && isOpen(item)) walk(item.children!, level + 1, item.id);
    });
  walk(items, 1, null);
  return out;
}

/** The ids of the ancestors of item `id`, outermost first; null when no item has that id. */
export function ancestorsOf(items: readonly TreeItem[], id: string): string[] | null {
  for (const t of items) {
    if (t.id === id) return [];
    const below = t.children ? ancestorsOf(t.children, id) : null;
    if (below) return [t.id, ...below];
  }
  return null;
}

/** The first item, depth first, that `match` accepts. */
export function findItem(items: readonly TreeItem[], match: (t: TreeItem) => boolean): TreeItem | null {
  for (const t of items) {
    if (match(t)) return t;
    const below = t.children ? findItem(t.children, match) : null;
    if (below) return below;
  }
  return null;
}

const FOLDER = svg`<path d="M1.5 3.5h4l1.5 1.5h7.5v8h-13z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"></path>`;
const FILE = svg`<path d="M3.5 1.5h6l3 3v10h-9z M9.5 1.5v3h3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"></path>`;

/**
 * Items in a tree, the children of each under it, folded and opened by the reader: files
 * and directories, say. It is one tab stop: Up and Down move between the items shown,
 * Right opens an item (then moves to its first child), Left closes it (or moves to its
 * parent), Home and End go to the first and the last, a letter to the next item of
 * that initial; Enter, Space or a click selects a selectable item (`cae-select`) and
 * opens or closes any other. The toggle before an item with children opens and closes
 * it (`cae-toggle`). The ancestors of `selected` are always open.
 *
 * @tagname cae-tree
 * @fires cae-select - `{id}`: an item was chosen with a click, Enter or Space
 * @fires cae-toggle - `{id, open}`: the reader opened or closed an item
 * @csspart tree - the list of items
 * @csspart item - an item's row
 * @csspart empty - what it shows with no items
 */
export class CaeTree extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; font-size: var(--font-size-md); }
      .tree { margin: 0; padding: 2px 0; }
      .row { display: flex; align-items: center; gap: 4px; min-height: 24px; padding: 0 8px 0 calc((var(--level) - 1) * 14px + 4px);
        border-radius: var(--radius-sm); cursor: pointer; white-space: nowrap; color: var(--text-2); }
      .row:hover { background: var(--raise); }
      .row[aria-selected='true'] { background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--text); box-shadow: inset 2px 0 0 var(--accent); }
      .row:focus-visible { outline-offset: -2px; }
      .twist { flex: none; display: inline-grid; place-items: center; width: 16px; height: 16px; color: var(--text-muted); border-radius: var(--radius-sm); }
      .twist svg { transition: transform 0.12s ease; }
      [aria-expanded='true'] > .twist svg { transform: rotate(90deg); }
      .twist:hover { color: var(--text); }
      .icon { flex: none; width: 16px; height: 16px; color: var(--text-muted); }
      .name { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
      .badge { flex: none; margin-left: 6px; font-size: 11px; padding: 0 6px; border-radius: var(--radius-pill); background: var(--raise); color: var(--text-2); }
      .badge[data-tone] { background: var(--tone-bg); color: var(--tone); }
      .badge[data-tone='done'] { background: none; color: var(--text-2); }
      .empty { color: var(--text-muted); font-size: var(--font-size-sm); padding: 4px 8px; }
      @media (prefers-reduced-motion: reduce) { .twist svg { transition: none; } }
    `,
  ];

  @property({ attribute: false }) items: readonly TreeItem[] = [];
  /** The selected item's id, or null. */
  @property({ attribute: false }) selected: string | null = null;
  /** What the tree is named to a screen reader. */
  @property() label = '';
  /** The visible words; English by default. */
  @property({ attribute: false }) strings: Partial<TreeStrings> = {};

  /** The reader's choice of open and closed items, by id, over each item's `open`. */
  @state() private opened = new Map<string, boolean>();
  /** The item that holds the tab stop. */
  @state() private focusId: string | null = null;

  private readonly isOpen = (t: TreeItem): boolean => this.opened.get(t.id) ?? t.open ?? true;

  override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('selected') && this.selected) {
      const up = ancestorsOf(this.items, this.selected);
      if (up?.some((id) => this.opened.get(id) !== true)) {
        const next = new Map(this.opened);
        for (const id of up) next.set(id, true);
        this.opened = next;
      }
    }
  }

  override updated(changed: PropertyValues<this>): void {
    if (changed.has('selected') && this.selected && !this.matches(':focus-within')) {
      this.rowOf(this.selected)?.scrollIntoView?.({ block: 'nearest' });
    }
  }

  private rowOf(id: string): HTMLElement | null {
    return this.renderRoot.querySelector<HTMLElement>(`[data-id="${CSS.escape(id)}"]`);
  }

  private setOpen(t: TreeItem, open: boolean): void {
    if (!hasChildren(t) || this.isOpen(t) === open) return;
    this.opened = new Map(this.opened).set(t.id, open);
    emit(this, 'cae-toggle', { id: t.id, open });
  }

  private choose(t: TreeItem): void {
    this.focusId = t.id;
    if (selectable(t)) emit(this, 'cae-select', { id: t.id });
    else this.setOpen(t, !this.isOpen(t));
  }

  private async moveTo(id: string): Promise<void> {
    this.focusId = id;
    await this.updateComplete;
    this.rowOf(id)?.focus();
  }

  private onKey(e: KeyboardEvent, rows: readonly TreeRow[], i: number): void {
    const row = rows[i]!;
    const t = row.item;
    let to: TreeRow | undefined;
    switch (e.key) {
      case 'ArrowDown':
        to = rows[i + 1];
        break;
      case 'ArrowUp':
        to = rows[i - 1];
        break;
      case 'Home':
        to = rows[0];
        break;
      case 'End':
        to = rows[rows.length - 1];
        break;
      case 'ArrowRight':
        if (hasChildren(t) && !this.isOpen(t)) this.setOpen(t, true);
        else if (hasChildren(t)) to = rows[i + 1];
        break;
      case 'ArrowLeft':
        if (hasChildren(t) && this.isOpen(t)) this.setOpen(t, false);
        else if (row.parent) to = rows.find((r) => r.item.id === row.parent);
        break;
      case 'Enter':
      case ' ':
        this.choose(t);
        break;
      default: {
        if (e.key.length !== 1 || e.ctrlKey || e.metaKey || e.altKey || !/\S/.test(e.key)) return;
        const k = e.key.toLowerCase();
        const order = [...rows.slice(i + 1), ...rows.slice(0, i)];
        to = order.find((r) => r.item.name.toLowerCase().startsWith(k));
        if (!to) return;
      }
    }
    e.preventDefault();
    if (to) void this.moveTo(to.item.id);
  }

  override render() {
    if (!this.items.length) return html`<div class="empty" part="empty">${withDefaults(DEFAULT_TREE_STRINGS, this.strings).empty}</div>`;
    const rows = visibleRows(this.items, this.isOpen);
    const stop = rows.find((r) => r.item.id === this.focusId) ?? rows.find((r) => r.item.id === this.selected) ?? rows[0];
    return html`<div class="tree" role="tree" part="tree" aria-label=${this.label || nothing}>
      ${rows.map((r, i) => this.row(r, i, rows, r === stop))}
    </div>`;
  }

  private row(r: TreeRow, i: number, rows: readonly TreeRow[], stop: boolean): TemplateResult {
    const t = r.item;
    const parent = hasChildren(t);
    const open = parent && this.isOpen(t);
    const directory = (t.icon ?? (parent ? 'directory' : 'file')) === 'directory';
    return html`<div
      class="row"
      part="item"
      role="treeitem"
      data-id=${t.id}
      tabindex=${stop ? 0 : -1}
      style="--level: ${r.level}"
      aria-level=${r.level}
      aria-setsize=${r.siblings}
      aria-posinset=${r.index + 1}
      aria-expanded=${parent ? String(open) : nothing}
      aria-selected=${selectable(t) ? String(t.id === this.selected) : nothing}
      @click=${() => this.choose(t)}
      @focus=${() => (this.focusId = t.id)}
      @keydown=${(e: KeyboardEvent) => this.onKey(e, rows, i)}
    >
      <span class="twist" aria-hidden="true" @click=${(e: Event) => {
        if (!parent) return;
        e.stopPropagation();
        this.focusId = t.id;
        this.setOpen(t, !open);
      }}>${parent ? html`<svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 1.5 7 5 3 8.5" fill="none" stroke="currentColor" stroke-width="1.5"></path></svg>` : nothing}</span>
      <svg class="icon" viewBox="0 0 16 16" aria-hidden="true">${directory ? FOLDER : FILE}</svg>
      <span class="name">${t.name}</span>
      ${t.badge ? statusChip('badge', { text: t.badge, tone: t.tone ?? 'neutral' }) : nothing}
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-tree': CaeTree;
  }
}
