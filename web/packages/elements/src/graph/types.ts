// A layered graph's model: what the host gives `<cae-layered-graph>` (`GraphInput`),
// and the order `arrange` finds for it (`Arrangement`). No word here is the host's:
// a state is an opaque id that `StateStyles` maps to a look.
import type { Fact } from '../primitives/fact-line.js';
import type { Tone } from '../core/tone.js';

/** How an edge is drawn: solid, or dashed (another kind of link). */
export type EdgeStyle = 'solid' | 'dashed';

/** One mark of a node: an item it stands for, drawn as a small shape in its state's look. */
export interface GraphMark {
  /** Unique in the graph: the selection id. */
  id: string;
  /** A key of `StateStyles`. */
  state: string;
  /** The accessible name: what it is, and its facts. */
  label: string;
  /** The tooltip. */
  tip?: string;
  /** A short text in the mark: a count. */
  badge?: string;
  /** A short name, as a chip shows it (a node drawn as a bar lists its failed marks by it); default: its series id. */
  name?: string;
  /** The mark opens an inner view: Enter and a double click send `cae-drill`, not `cae-activate`. */
  drill?: boolean;
}

export interface GraphNodeInput {
  id: string;
  label: string;
  /** The tooltip of its name. */
  tip?: string;
  /** The accessible name of the node: its facts in sentences; default: `label`. */
  summary?: string;
  /** The innermost cluster it is drawn in, or null. */
  cluster: string | null;
  /** Icon names (`registerIcon`) before its label. */
  icons?: readonly string[];
  /** An accent along its side: an identity, not a status. */
  accent?: boolean;
  /** It has an inner view: it is drawn as a stack, and Enter and a double click send `cae-drill`. */
  drill?: boolean;
  /** One per series id (`GraphInput.series`), null where the series has no mark here; [] when it has no series marks. */
  marks: readonly (GraphMark | null)[];
  /** Its marks outside any series. */
  loose: readonly GraphMark[];
  /** Its items by state (the states of `StateStyles`): the bar a node with many marks draws. */
  counts: Readonly<Record<string, number>>;
  /** Its header's count ("28/30") and its words. */
  progress: { done: number; total: number; label: string };
  /** The line under its marks ("1 failed | 1 not started"). */
  notes?: readonly Fact[];
  /** Its frame's tone: failed, running or done. */
  look?: Tone;
}

/** A box of nodes (and of other clusters) in a layered graph. */
export interface GraphClusterInput {
  id: string;
  /** The cluster it is in, or null at the top level. */
  parent: string | null;
  /** The name in its header. */
  label: string;
  /** The tooltip of its name. */
  tip?: string;
  /** A fact beside its name ("up to 3 passes"). */
  note?: string;
  /** A second line under its name, and its tooltip. */
  detail?: string;
  detailTip?: string;
  /** Its accessible name; default: `label`. */
  summary?: string;
  /** In the node table, a node in it links to it by a chip (`note` with the cluster's icon): the chip's accessible name and tooltip. */
  chipLabel?: string;
  chipTip?: string;
  /** It has an inner view: Enter and a double click send `cae-drill`. */
  drill?: boolean;
  /** Its content repeats: it draws a return from its last layer to its first. */
  cycle: boolean;
}

export interface GraphEdgeInput {
  from: string;
  to: string;
  style: EdgeStyle;
  /** How many links it stands for. */
  weight: number;
  /** False: it closes a cycle (a cluster's next round); it never sets the layers, and is drawn only as the cluster's return. */
  ranks: boolean;
}

/** An edge from outside the graph, drawn from a named stub. */
export interface GraphStubInput {
  id: string;
  label: string;
  to: string;
  style: EdgeStyle;
  weight: number;
}

export interface GraphInput {
  /** The ids that line marks up across nodes, in drawing order. */
  series: readonly string[];
  nodes: readonly GraphNodeInput[];
  clusters: readonly GraphClusterInput[];
  edges: readonly GraphEdgeInput[];
  stubs: readonly GraphStubInput[];
}

/** Where a graph's items are: give it back to `arrange` to keep them there. */
export interface GraphOrder {
  /** The top level's layers: nodes, clusters and stubs. */
  layers: string[][];
  clusters: Record<string, string[][]>;
}

/** One place an edge passes: a slot (`id`) of a container (`in`: '' for the top level, else a cluster id). */
export interface RouteStep {
  id: string;
  in: string;
}

/**
 * A drawn edge (or a stub's), as the slots it passes from its source to its target:
 * a point (`~...`) on every layer it crosses, and a cluster's id where it leaves or
 * enters that cluster.
 */
export interface EdgeRoute {
  from: string;
  to: string;
  style: EdgeStyle;
  steps: RouteStep[];
}

/** A cluster as arranged: its items (node and cluster ids) by layer, each layer in drawing order. */
export interface ClusterLayers {
  id: string;
  parent: string | null;
  /** It draws a return from its last layer to its first (`GraphClusterInput.cycle`). */
  cycle: boolean;
  layers: string[][];
}

/** The order `arrange` finds: layers, the order in each, and the slots each edge passes. */
export interface Arrangement {
  /** Every node id, in drawing order. */
  drawn: string[];
  /** The top level's node and cluster ids by layer (no stubs), each layer in drawing order. */
  layers: string[][];
  /** Every cluster, in the input's order. */
  clusters: ClusterLayers[];
  /** One per input edge: it goes back (closes a cycle) and is not drawn. */
  back: boolean[];
  /** Each container's slots by layer, in drawing order: '' for the top level, a cluster's id for its inside. */
  slots: Record<string, string[][]>;
  /** The drawn edges and the stubs' edges, with the slots they pass. */
  routes: EdgeRoute[];
  order: GraphOrder;
}
