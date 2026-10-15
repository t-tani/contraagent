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
 * the tasks that will not run, how long the run took, its cost and usage, running. Before the feed has
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
  // Tasks deferred, or queued when the run ended: they will not run (the run list counts them).
  const notRun = summary.tasks.not_run ? stateCount('not_run', summary.tasks.not_run) : '';
  return facts(msg(str`${c.doneTotal} of ${c.total} tasks done`), notRun, tail);
}

/** The history bar's count, as the overview counts: "23 attempts | 4 not started". */
export function triesLine({ tries, notStarted }: RunDerived['tries']): string {
  return facts(tries === 1 ? msg('1 attempt') : msg(str`${tries} attempts`), notStarted ? stateCount('not_started', notStarted) : '');
}

/** A stub run's mark (`RunSummary.stub`): its tasks were played by the stub agent. */
export const stubLabel = (): string => msg('stub agent', { desc: 'A run whose tasks a coding agent with scripted replies played' });

/** What a stub run's mark means, for its tooltip. */
export const stubTip = (): string => msg('Tasks played by the stub agent with scripted replies (stub)');

/** A replay's mark (`RunSummary.replay`): its agent tasks played their recordings. */
export const replayLabel = (): string => msg('replay', { desc: 'A run whose agent sessions were played from the recordings of an earlier run' });

/** What a replay's mark means, for its tooltip: where its recordings are. */
export const replayTip = (dir: string): string => msg(str`Agent sessions played from the recordings in ${dir} (replay)`);

/**
 * A replay that also launched (`RunSummary.replay` with `stub` false, `record_missing`):
 * some attempts played their recordings, the others ran and were recorded. Only
 * then is each played attempt (`JournalRow.replayed`) marked: in a replay that
 * launched nothing, the run's mark says it of every attempt.
 */
export const mixedReplay = (r: Pick<RunSummary, 'stub' | 'replay'> | undefined): boolean => !!r?.replay && !r.stub;

/** A replay that also launched: its mark. */
export const mixedReplayLabel = (): string =>
  msg('replay and new sessions', { desc: 'A run that played some attempts from recordings and ran the others as new agent sessions' });

/** What that mark means, for its tooltip: where its recordings are. */
export const mixedReplayTip = (dir: string): string =>
  msg(str`Agent sessions played from the recordings in ${dir}, and new agent sessions recorded there (replay, record_missing)`);

/** An attempt played from its recording (`JournalRow.replayed`), in a replay that also launched. */
export const replayedLabel = (): string => msg('replayed', { desc: 'An attempt played from its recording, not run again' });

/** What that mark means, for its tooltip. */
export const replayedTip = (): string => msg('Played from a recording (replayed)');

/** The mark beside a run's name: a replay (one that also launched, or not), else a stub run; null for a run of coding agents. */
export function runMark(r: Pick<RunSummary, 'stub' | 'replay'> | undefined): { text: string; title: string } | null {
  if (r?.replay && mixedReplay(r)) return { text: mixedReplayLabel(), title: mixedReplayTip(r.replay) };
  if (r?.replay) return { text: replayLabel(), title: replayTip(r.replay) };
  if (r?.stub) return { text: stubLabel(), title: stubTip() };
  return null;
}
