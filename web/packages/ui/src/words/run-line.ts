// The monitor's one-line summaries of a run: the header's run line and the
// history bar's count.
import { deriveRun, elapsedS, runAccounts, spendOf, type RunDerived, type RunState, type RunSummary } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, usd } from './format.js';
import { stateCount } from './outcome.js';
import { accountsLine } from './quota.js';

/** Each account's latest subscription reading, busiest weekly first: from the live journal once replayed, else the run list's. */
export const runLineAccounts = (state: RunState, summary: RunSummary) =>
  state.ready ? runAccounts(state.journal) : (summary.quota ?? []);

/**
 * The header's run line: tasks that ended well out of all tasks (not attempts),
 * how long the run took, its cost and usage, running. Before the feed has
 * replayed, no count: the run list's figures only.
 */
export function runLine(state: RunState, summary: RunSummary, derived: RunDerived = deriveRun(state.journal, state.plan)): string {
  const took = elapsedS(summary);
  // The live journal is fresher than the run list (polled); before the replay is in, the run list's figure.
  const spent = state.ready ? spendOf(state.journal)?.cost : summary.cost_usd;
  const cost = spent !== null && spent !== undefined ? usd(spent) : '';
  const usage = accountsLine(runLineAccounts(state, summary));
  const tail = facts(took == null ? '' : msg(str`took ${fmtDur(took)}`), cost, usage, summary.running ? msg('running') : '');
  if (!state.ready) return tail; // the feed is still replaying: no count yet rather than a wrong one
  const c = derived.counts;
  return facts(msg(str`${c.doneTotal} of ${c.total} tasks done`), tail);
}

/** The history bar's count, as the overview counts: "23 attempts | 4 not started". */
export function triesLine({ tries, notStarted }: RunDerived['tries']): string {
  return facts(tries === 1 ? msg('1 attempt') : msg(str`${tries} attempts`), notStarted ? stateCount('not_started', notStarted) : '');
}

/** A stub run's mark (`RunSummary.stub`): its tasks were played by the stub agent. */
export const stubLabel = (): string => msg('stub agent', { desc: 'A run whose tasks a coding agent with scripted replies played' });
