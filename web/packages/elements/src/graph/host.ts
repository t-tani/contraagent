// What the graph's views read from `cae-layered-graph` and call on it. Each view is
// a function of the element (`GraphHost`, its private members included) that renders
// into its shadow root.
import type { ReactiveControllerHost } from 'lit';
import type { StateStyles } from '../primitives/states.js';
import type { CardController } from './card.js';
import type { GraphLayout } from './layout.js';
import { markGrid } from './marks.js';
import type { PanZoomController } from './pan-zoom.js';
import type { LayeredGraphStrings } from './strings.js';
import type { Arrangement, DrawnGraph, GraphClusterInput, GraphMark, GraphNode } from './types.js';

/** The failed marks a node drawn as a bar lists by name. */
export const BAR_LIST = 8;

/**
 * The element as its views see it: what it shows, the state the views change
 * (each change renders the element again), its controllers and what it sends.
 */
export interface GraphHost extends ReactiveControllerHost, HTMLElement {
  readonly renderRoot: ParentNode;
  /** The graph, its nodes with their defaults. */
  readonly drawn: DrawnGraph;
  readonly arr: Arrangement;
  readonly states: StateStyles;
  readonly words: LayeredGraphStrings;
  readonly selected: string | null;
  readonly nodes: ReadonlyMap<string, GraphNode>;
  readonly clusters: ReadonlyMap<string, GraphClusterInput>;
  /** Where everything is drawn, and whether it was drawn for this graph (`key`). */
  readonly lay: GraphLayout | null;
  readonly laidOut: boolean;
  /** Top to bottom. */
  readonly down: boolean;
  readonly barAt: number;
  /** The node table is shown. */
  readonly asTable: boolean;
  /** The series (or a mark's id, for a mark outside any series) under the pointer or focus. */
  hover: string | null;
  /** Each group's focused mark (roving tabindex): one tab stop per group. */
  readonly active: Map<string, number>;
  readonly pz: PanZoomController;
  readonly card: CardController;
  renderIcon(name: string): unknown;
  /** The series (or mark id) highlighted, and the marks it lights. */
  lit(): { key: string | null; on: ReadonlySet<string> | null };
  /** Select an item by its id (null: none). */
  select(id: string | null): void;
  /** Focus moved by the reader selects what it is on; focus put back does not. */
  focusSelect(id: string): void;
  /** An item's action: Enter, a double click, a card's first link. */
  act(id: string): void;
  /** Enter a cluster's inner view. */
  drill(id: string): void;
  /** The view switch. */
  showView(view: 'graph' | 'table'): void;
}

/** A mark in a node, with its series id ('' outside any series). */
export interface Slot {
  m: GraphMark;
  series: string;
}

/** How a group of marks lays out. */
export interface Grid {
  cols: number;
  size: number;
  gap: number;
}

/** A group of marks with one tab stop: a node's marks, or the failed marks a node drawn as a bar lists. */
export interface MarkGroup {
  id: string;
  slots: (Slot | null)[];
  grid: Grid;
}

/** A node's marks in slot order: one per series (null where the series has none here), then those outside any series. */
export const slotsOf = (n: Pick<GraphNode, 'marks' | 'loose'>, series: readonly string[]): (Slot | null)[] => [
  ...n.marks.map((m, i) => (m ? { m, series: series[i] ?? '' } : null)),
  ...n.loose.map((m) => ({ m, series: '' })),
];

/** A group's grid: the graph's, so a series sits at one place in every node; a group without series lays out its own few marks. */
export function gridOf(n: Pick<GraphNode, 'marks' | 'loose'>, series: number): Grid {
  const slots = n.marks.length + n.loose.length;
  const g = markGrid(n.marks.length ? series : slots);
  return { cols: Math.min(g.cols, Math.max(1, slots)), size: g.size, gap: g.size >= 10 ? 4 : 2 };
}

/** The first slot that holds a mark. */
export function firstMark(slots: readonly (Slot | null)[]): number {
  return Math.max(0, slots.findIndex((m) => m !== null));
}

/** What a mark highlights: its series, or itself outside any series. */
export const hlKeyOf = (s: Slot): string => s.series || s.m.id;
