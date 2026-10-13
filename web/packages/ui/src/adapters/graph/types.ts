// The pipeline graph's model: one layer of the run's flow, as `project` reads it
// from the plan and `layerGraph` gives it arranged (`arrange` of @contraagent/elements).
import type { PlanGroup, TaskState } from '@contraagent/api';
import type { Arrangement } from '@contraagent/elements/graph';

/** A layer segment that enters a loop box: `loop:<line>`, `loop:<outer>.<inner>` for a nested one. */
export const LOOP_SEGMENT = 'loop:';

/** One mark of a node: a unit's tasks (a kind node), or a unit's flow calls (a function node). */
export interface LayerMark {
  /** The task it opens (the running one, else the last), or the flow call it stands for. */
  key: string;
  unit: string;
  state: TaskState;
  /** The tasks it stands for. */
  count: number;
  keys: string[];
  /** A function node's mark: the function (`module.qualname`) it enters. */
  flow?: string;
  /** In a loop box: the passes its unit's tasks (or flow calls) of this node ran in, when more than 1. */
  passes?: number;
  /** A function node's mark: its tasks by state (those of the flow calls it started included). */
  counts?: NodeCounts;
  /** A function node's mark whose flow call raised or was closed: what it raised (`<type>: <message>`), '' when not recorded. */
  error?: string;
}

export type NodeCounts = Pick<PlanGroup, 'total' | 'done' | 'failed' | 'running' | 'pending' | 'skipped' | 'blocked'>;

export interface GraphNode {
  id: string;
  /** `kind`: tasks created in the layer's own function; `flow`: tasks created in a function it called. */
  type: 'kind' | 'flow';
  /** The plan group's id, or the function's `module.qualname`. */
  name: string;
  label: string;
  /** The kinds of its tasks. */
  kinds: string[];
  /** A kind node: who runs its tasks (`mixed` when its kinds differ); null for a function node. */
  executor: 'agent' | 'python' | 'mixed' | null;
  /** The loop box it is drawn in (its innermost), or null. */
  box: string | null;
  /** One slot per unit of the layer, in the layer's unit order: null where the unit has no mark here. Empty for a node without units. */
  units: (LayerMark | null)[];
  /** Its marks without a unit. */
  single: LayerMark[];
  /** Its tasks also wait for each other. */
  inOrder: boolean;
  /** Its tasks by state (in a function node, those of the flow calls they started included); in a loop box, each unit's latest pass. */
  counts: NodeCounts;
  /** A function node: its flow calls (in a loop box, each unit's latest pass); 0 for a kind node. */
  calls: number;
  /** A function node: those of its flow calls that raised or were closed. */
  errors: number;
}

/** The nodes created by one loop of the layer's function; a nested loop is a box inside it. */
export interface LoopBox {
  /** `loop:<line>`, `loop:<outer>.<inner>` for a nested loop. */
  id: string;
  /** The loop's first line. */
  loop: number;
  /** The file the loop is in (the layer's function's file, as recorded); '' when not known. */
  file: string;
  /** The loop box this one is nested in, or null when it is at the layer's top level. */
  parent: string | null;
  /** Its last pass: the most passes of this loop (never a nested loop's) in one run of it. */
  passes: number;
  /** How many units ran each number of passes of it, fewest first: `[[1, 4], [2, 1]]`. */
  spread: [passes: number, units: number][];
  /** Its items (node ids and nested loop box ids) by layer, each layer in drawing order. */
  layers: string[][];
}

export interface GraphEdge {
  from: string;
  to: string;
  /** Tasks of `to` joined to a task of `from`. */
  tasks: number;
  /** `after`: waits for its output; `created`: created after its result (and does not wait for its output). */
  type: 'after' | 'created';
  /** Some task of it joins a task in the same pass of every loop around both ends: it sets the layers (else it goes back to a loop's next pass). */
  samePass: boolean;
  /** It goes back to a loop's next pass (or otherwise closes a cycle): the loop box stands for it, it is not drawn. */
  back: boolean;
}

/** An edge from a task outside the layer, named by the node it is in at the nearest layer that holds both. */
export interface GraphStub {
  id: string;
  label: string;
  to: string;
  tasks: number;
  type: 'after' | 'created';
}

/** A layer as the plan has it, before it is arranged: its nodes in the plan's order, its loop boxes without their layers. */
export interface LayerModel {
  /** The layer: function names, outermost first. */
  path: string[];
  nodes: GraphNode[];
  boxes: LoopBox[];
  edges: GraphEdge[];
  stubs: GraphStub[];
  /** The units with a mark in this layer, in the order the run first scheduled them. */
  units: string[];
}

/** A layer of the run's flow, arranged: its nodes in drawing order, each loop box with its layers, each edge that goes back marked. */
export interface LayerGraph extends Arrangement {
  /** The layer: function names, outermost first. */
  path: string[];
  /** Every node, in drawing order. */
  nodes: GraphNode[];
  boxes: LoopBox[];
  edges: GraphEdge[];
  stubs: GraphStub[];
  /** The units with a mark in this layer, in the order the run first scheduled them. */
  units: string[];
}
