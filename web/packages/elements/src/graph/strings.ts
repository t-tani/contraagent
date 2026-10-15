// A layered graph's words: English defaults, each replaceable (`strings`).

export interface LayeredGraphStrings {
  /** The view switch: its options and its label. */
  graph: string;
  table: string;
  view: string;
  /** The zoom buttons' names and tooltips, and the button back to the whole drawing. */
  zoomIn: string;
  zoomInTip: string;
  zoomOut: string;
  zoomOutTip: string;
  showAll: string;
  /** The key hints of the drawing, the node table and a mark matrix (Escape's hint is added after them). */
  graphKeys: readonly string[];
  tableKeys: readonly string[];
  matrixKeys: readonly string[];
  /** Escape's hint with a selection, and without one ('' when Escape does nothing then). */
  clearKey: string;
  upKey: string;
  /** The selection card's accessible name. */
  inspector: string;
  /** A stub's tooltip: it stands for something outside the graph. */
  stubTip: string;
  /** The marks a node drawn as a bar does not list: "+3". */
  more: (n: number) => string;
  /** A node's count without `progress`: its marks of the tone `done`, of all its marks ("2 of 3 done"). */
  progress: (done: number, total: number) => string;
  /** Legend words: a badge in a mark, the two edge styles, a cluster's return, an inner view. */
  badge: string;
  solidEdge: string;
  dashedEdge: string;
  cycle: string;
  drill: string;
  /** The open and close controls of an item that can be drawn open ("Show inside", "Hide inside"). */
  open: string;
  close: string;
  /** Icon name → its legend word; an icon drawn and named here is in the legend, in this order. */
  iconNames: Readonly<Record<string, string>>;
  /** The node table's headers, the empty list, and a node's name in a cluster. */
  nameHeader: string;
  statusHeader: string;
  solidHeader: string;
  dashedHeader: string;
  laterHeader: string;
  none: string;
  inCluster: (label: string) => string;
  /** Names as a list: "a, b, and c". */
  list: (items: readonly string[]) => string;
}

export const DEFAULT_LAYERED_GRAPH_STRINGS: Readonly<LayeredGraphStrings> = {
  graph: 'Graph',
  table: 'Table',
  view: 'View',
  zoomIn: 'Zoom in',
  zoomInTip: 'Zoom in (Ctrl + scroll)',
  zoomOut: 'Zoom out',
  zoomOutTip: 'Zoom out (Ctrl + scroll)',
  showAll: 'Show all',
  graphKeys: ['Tab: next node', 'Arrow keys: marks', 'Shift + arrow keys: earlier and later nodes', 'Enter: open'],
  tableKeys: ['Tab: next row', 'Enter: open'],
  matrixKeys: ['Arrow keys: marks', 'Enter: open'],
  clearKey: 'Esc: clear selection',
  upKey: '',
  inspector: 'Selected item',
  stubTip: 'Outside this graph',
  more: (n) => `+${n}`,
  progress: (done, total) => `${done} of ${total} done`,
  badge: 'count',
  solidEdge: 'link',
  dashedEdge: 'other link',
  cycle: 'next round',
  drill: 'has an inner view',
  open: 'Show inside',
  close: 'Hide inside',
  iconNames: {},
  nameHeader: 'Name',
  statusHeader: 'Status',
  solidHeader: 'Earlier',
  dashedHeader: 'Dashed link from',
  laterHeader: 'Later',
  none: 'none',
  inCluster: (label) => `${label} in the cluster`,
  list: (items) => new Intl.ListFormat('en', { type: 'conjunction' }).format(items),
};
