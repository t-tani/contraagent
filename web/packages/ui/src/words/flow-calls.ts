// Where a flow call stopped (`FlowCallNode.raised_at`, `raised_by`), and the tasks it
// created that no flow awaited (`FlowCallNode.unawaited`).
import { runRelative, type FlowCallNode } from '@contraagent/api';
import { msg, str } from '@lit/localize';

/** `module.qualname` as the graph names a function: its last part. */
const shortFn = (fn: string): string => fn.slice(fn.lastIndexOf('.') + 1) || fn;

/** Where an exception left a flow call's own code: `flow.py:42`; '' when not recorded. */
export function raisedWhere(f: Pick<FlowCallNode, 'raised_at'>, run = ''): string {
  const at = f.raised_at;
  return at ? `${runRelative(at.file, run)}:${at.line}` : '';
}

/** On the failed task: "This failure stopped review_loop at flow.py:42" (without a place: "This failure stopped review_loop"). */
export function stoppedAt(f: FlowCallNode, run = ''): string {
  const fn = shortFn(f.function);
  const where = raisedWhere(f, run);
  return where ? msg(str`This failure stopped ${fn} at ${where}`) : msg(str`This failure stopped ${fn}`);
}

/** On a flow call that raised: "Stopped at flow.py:42" with the failed task's name, or its own error. */
export function stoppedHere(f: FlowCallNode, by: string, run = ''): string {
  const where = raisedWhere(f, run);
  if (by) return where ? msg(str`Stopped at ${where} by the failure of ${by}`) : msg(str`Stopped by the failure of ${by}`);
  return where ? msg(str`Stopped at ${where}`) : '';
}

/** A count of a top flow call's unawaited tasks: "2 tasks not awaited". */
export function unawaitedCount(n: number): string {
  return n === 1 ? msg('1 task not awaited') : msg(str`${n} tasks not awaited`);
}

/** The tooltip of unawaited tasks. */
export const unawaitedTip = (): string =>
  msg('Tasks whose result no flow awaited, ordered a task after or returned (unawaited); they ran for their output files and changes');
