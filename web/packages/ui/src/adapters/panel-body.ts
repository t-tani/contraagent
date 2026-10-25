// A pipeline's own view (`monitor.Panel`) → what the generic elements take: a table
// body's columns and rows for `<cae-data-table>`, its tiles for `<cae-stat-tiles>`, a tree body's nodes for `<cae-tree>`.
import type { PanelTile, TableBody, TableColumn, TreeBody, TreeNode } from '@contraagent/api';
import type { DataColumn } from '@contraagent/elements/data-table';
import type { StatTile } from '@contraagent/elements/tiles';
import type { TreeItem } from '@contraagent/elements/tree';
import type { Tone } from '@contraagent/elements';
import { html } from 'lit';
import { cellText } from '../words/panels.js';

/** A row of a table body: a value per column id, and its status (`_tone`). */
export type BodyRow = Readonly<Record<string, unknown>> & { _tone?: Tone | null };

const TONES: readonly string[] = ['failed', 'attention', 'done', 'running', 'muted', 'neutral'];

/** A row's status, when it names one the monitor knows. */
export const rowTone = (r: BodyRow): Tone | undefined => (typeof r._tone === 'string' && TONES.includes(r._tone) ? r._tone : undefined);

/** The formats of numbers: their columns are right-aligned. */
const NUMERIC = new Set(['usd', 'pct', 'duration', 'tokens', 'number']);

/** A cell as the text it is ordered by; an object's is written once. */
const objectKeys = new WeakMap<object, string>();
const cellKey = (v: unknown): string => {
  if (typeof v === 'string') return v;
  if (typeof v !== 'object' || v === null) return JSON.stringify(v);
  let k = objectKeys.get(v);
  if (k === undefined) objectKeys.set(v, (k = JSON.stringify(v)));
  return k;
};

/** The order `localeCompare` gives, made once. */
const text = new Intl.Collator();

/** The order of two cells: numbers by value, then text; empty cells last. */
function compareCells(a: unknown, b: unknown): number {
  const empty = (v: unknown) => v === null || v === undefined || v === '';
  if (empty(a) || empty(b)) return empty(a) === empty(b) ? 0 : empty(a) ? 1 : -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return text.compare(cellKey(a), cellKey(b));
}

/** `v` as a URL a cell may lead to: http or https only; null for anything else. */
export function cellUrl(v: unknown): string | null {
  if (typeof v !== 'string' || !/^https?:\/\//i.test(v.trim())) return null;
  try {
    const u = new URL(v.trim());
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null;
  } catch {
    return null;
  }
}

/**
 * The columns of a table body: each cell written by its column's format, a number
 * right-aligned, a `bar` column with a bar, a `link` column a link to its row's URL.
 */
export function bodyColumns(body: TableBody): DataColumn<BodyRow>[] {
  return body.columns.map((c: TableColumn, i): DataColumn<BodyRow> => {
    const numeric = c.format ? NUMERIC.has(c.format) : body.rows.some((r) => typeof (r as BodyRow)[c.id] === 'number');
    const top = c.bar ? Math.max(0, ...body.rows.map((r) => Number((r as BodyRow)[c.id]) || 0)) : 0;
    return {
      id: c.id,
      header: c.label,
      tip: c.tip ?? undefined,
      align: c.align ?? (numeric ? 'end' : 'start'),
      rowHeader: i === 0,
      compare: (a, b) => compareCells(a[c.id], b[c.id]),
      text: (r) => cellText(r[c.id], c.format),
      cell: (r) => {
        const v = r[c.id];
        const text = cellText(v, c.format);
        const url = c.link ? cellUrl(r[c.link]) : null;
        if (url) return html`<a href=${url} target="_blank" rel="noopener noreferrer">${text}</a>`;
        if (!c.bar || typeof v !== 'number') return text;
        // A measure, not a verdict: the bar stays neutral; the row's tone marks its status.
        return html`${text}<span class="jdur" aria-hidden="true"><i style="width: ${top > 0 ? (100 * Math.max(0, v)) / top : 0}%"></i></span>`;
      },
    };
  });
}

/** A tree body as `<cae-tree>` takes it, and each node by its id. */
export interface BodyTree {
  items: TreeItem[];
  /** Each node, by its id (its own, else the names from the top joined by `/`). */
  nodes: Map<string, TreeNode>;
  /** The node selected first: the body's `selected`, else the first node with code; null when none has code. */
  first: string | null;
}

/**
 * A tree body's nodes as tree items: each node's id its own or the names from the top
 * joined by `/` (as the monitor's model names them), selectable when it has code or a link.
 */
export function bodyTree(body: TreeBody): BodyTree {
  const nodes = new Map<string, TreeNode>();
  let first: string | null = null;
  const walk = (list: readonly TreeNode[], parent: string): TreeItem[] =>
    list.map((n) => {
      const path = parent ? `${parent}/${n.name}` : n.name;
      const id = n.id ?? path;
      nodes.set(id, n);
      if (first === null && n.code) first = id;
      return {
        id,
        name: n.name,
        icon: n.icon ?? null,
        badge: n.badge ?? null,
        tone: n.tone ?? null,
        open: n.open ?? true,
        selectable: !!n.code || !!n.link,
        children: n.children?.length ? walk(n.children, path) : null,
      };
    });
  const items = walk(body.nodes, '');
  return { items, nodes, first: body.selected ?? first };
}

/** A body's tiles as `<cae-stat-tiles>` takes them. */
export const bodyTiles = (tiles: readonly PanelTile[]): StatTile[] =>
  tiles.map((t) => ({ id: t.id, label: t.label, value: t.value, tone: t.tone ?? undefined, tip: t.tip ?? undefined, sub: t.sub ?? [] }));
