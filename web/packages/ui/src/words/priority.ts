// Words for a task's priority (`PlanNode.priority`): a tie-breaker in the queue's order.
import { msg, str } from '@lit/localize';

/** A task's priority as a fact: `Priority 2`; '' for the default, 0. */
export const priorityText = (p: number | null | undefined): string => (p ? msg(str`Priority ${p}`) : '');

/** What a task's priority is, for its tooltip. */
export const priorityTip = (): string => msg("Tie-breaker in the queue's order (priority)");
