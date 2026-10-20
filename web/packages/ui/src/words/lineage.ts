// How a task is joined to an earlier one (`Lineage`), in the words of the graph's
// edges: each word names the edge from the earlier task to the later one, in the
// task's earlier and later tasks alike. And an input file's check at the start.
import type { InputFileCheck, Lineage } from '@contraagent/api';
import { msg } from '@lit/localize';

/** A lineage as the graph's legend names its edge: given output (solid), runs after (dotted), created after result (dashed). */
export function lineageWord(l: Lineage): string {
  switch (l) {
    case 'given_from':
      return msg('given output', { id: 'edge-given', desc: 'An edge of the pipeline graph: the later task was given the earlier task\'s output (given_from)' });
    case 'after':
      return msg('runs after', { id: 'edge-after', desc: 'An edge of the pipeline graph: the later task waits for the earlier task and is not given its output (order only)' });
    case 'created_from':
      return msg('created after result', { id: 'edge-created', desc: 'An edge of the pipeline graph: the later task was created after the earlier task\'s result (created_from)' });
  }
}

/** A lineage's tooltip: the field of the plan it comes from. */
export function lineageTip(l: Lineage): string {
  switch (l) {
    case 'given_from':
      return msg('Its output is in the params of the later task (given_from)');
    case 'after':
      return msg('The later task waits for it and is not given its output (after)');
    case 'created_from':
      return msg('Its result reached the flow call just before the flow call created the later task (created_from)');
  }
}

/** An input file's check as its task was about to start. */
export function inputFileCheckWord(c: InputFileCheck): string {
  switch (c) {
    case 'passed':
      return msg('same content at the start');
    case 'refused':
      return msg('changed before the start');
    case 'not_checked':
      return msg('not checked', { id: 'input-file-not-checked', desc: 'An input file whose task has not started: its content was not compared yet' });
  }
}
