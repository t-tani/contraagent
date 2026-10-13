// What the pipeline graph's parts read from `ca-pipeline-graph`: the run, the layer
// shown, and its model as the plan has it (the generic graph draws it).
import type { JournalRow, Plan } from '@contraagent/api';
import type { TaskLinks } from '../../../adapters/graph/highlight.js';
import type { PassMatrix } from '../../../adapters/graph/matrix.js';
import type { LayerGraph } from '../../../adapters/graph/types.js';

export interface PipelineHost {
  readonly el: HTMLElement;
  readonly plan: Plan;
  readonly journal: readonly JournalRow[];
  /** The run id: paths in a cause are shown relative to it. */
  readonly run: string;
  readonly live: boolean;
  /** The route's selection and pinned unit. */
  readonly sel: string;
  readonly unit: string;
  /** The layer shown (its segments), and the layer the graph opens on. */
  readonly segments: readonly string[];
  readonly auto: readonly string[];
  /** The layer, arranged as it is drawn. */
  readonly graph: LayerGraph;
  /** A loop's passes, when the layer shown is a loop. */
  readonly matrix: PassMatrix | null;
  readonly links: TaskLinks;
}
