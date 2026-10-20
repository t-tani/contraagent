// A task's states by severity: the one a mark of several tasks shows.
import type { PlanNode, TaskState } from '@contraagent/api';

export const SEVERITY: Record<TaskState, number> = { failed: 7, running: 6, blocked: 5, partial: 4, pending: 3, cancelled: 2, skipped: 1, done: 0 };

/** The state a mark of several tasks shows: the most severe of them. */
export const worstState = (nodes: readonly PlanNode[]): TaskState =>
  nodes.reduce<TaskState>((a, n) => (SEVERITY[n.state] > SEVERITY[a] ? n.state : a), 'done');

export const worstOf = (states: readonly TaskState[]): TaskState => states.reduce<TaskState>((a, s) => (SEVERITY[s] > SEVERITY[a] ? s : a), 'done');
