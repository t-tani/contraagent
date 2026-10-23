// The run in numbers, as the tiles of `<cae-stat-tiles>` (`ca-kpis`): tasks and
// how they ended, attempts, failed attempts, agent time, retries, corrections
// and model switches, from the journal. Pure.
import { inputProblems, isLaunched, isPython, retries, spendByKind, spendOf, totalTokens, type JournalRow, type RunDerived, type TaskOutcome } from '@contraagent/api';
import type { Fact } from '@contraagent/elements/primitives';
import type { StatTile } from '@contraagent/elements/tiles';
import { msg, str } from '@lit/localize';
import { problemTone } from '../lib/tone.js';
import { correctionCount, hadFixup } from './filters.js';
import { factList, facts, fmtDur, kindUnit, tokenCount, usd } from '../words/format.js';
import { stateCount } from '../words/index.js';
import { retryTip } from '../words/attempts.js';
import { correctionTip } from '../words/contract.js';
import { modelSwitchTip } from '../words/hops.js';

/**
 * The run's figures, from the journal. Only tries that ran count: a task
 * refused before launch (`invalid_input`) has a row but is not a try, not an
 * agent session and not a failed attempt; tasks are counted by `deriveRun`.
 */
export interface Kpis {
  /** Tries that ran. */
  attempts: number;
  python: number;
  /** Agent sessions: tries an agent ran. */
  launches: number;
  /** Tries that ran and failed. */
  bad: number;
  launchWall: number;
  pythonWall: number;
  /** Tries after a task's first, and the tasks they belong to. */
  retries: number;
  retriedTasks: number;
  /** The keys of the tasks that were retried / had fix-ups / switched models (to name or open one directly when it is the only one). */
  retriedKeys: string[];
  fixupKeys: string[];
  switchKeys: string[];
  /** Fix-ups (sessions resumed with check errors), and the tasks that had any. */
  fixups: number;
  fixupTasks: number;
  /** Model switches after a rate limit, and the tasks that switched. */
  switches: number;
  switchTasks: number;
}

export function kpis(journal: readonly JournalRow[]): Kpis {
  const ran = journal.filter(isLaunched);
  const py = ran.filter(isPython);
  const llm = ran.filter((e) => !isPython(e));
  const wall = (xs: readonly JournalRow[]) => xs.reduce((a, e) => a + (e.wall_s || 0), 0);
  const keys = (xs: readonly JournalRow[]) => [...new Set(xs.map((e) => e.key))];
  const tasks = (xs: readonly JournalRow[]) => keys(xs).length;
  const retried = retries(journal);
  const fixed = ran.filter(hadFixup);
  const switched = ran.filter((e) => (e.hops || []).length > 1);
  return {
    attempts: ran.length,
    python: py.length,
    launches: llm.length,
    bad: ran.filter((e) => !e.ok).length,
    launchWall: wall(llm),
    pythonWall: wall(py),
    retries: retried.length,
    retriedTasks: tasks(retried),
    retriedKeys: keys(retried),
    fixupKeys: keys(fixed),
    fixups: fixed.reduce((a, e) => a + correctionCount(e), 0),
    fixupTasks: tasks(fixed),
    switches: switched.reduce((a, e) => a + (e.hops || []).length - 1, 0),
    switchTasks: tasks(switched),
    switchKeys: keys(switched),
  };
}

/** What a tile's link opens: one task (`key`), or the history filtered by `stop` (`bad`, `invalid_input`, `retried`, `fixup`). */
export type KpiAction = { key: string } | { stop: string };

/** A tile's action id (`StatTile.action.id`) as what it opens. */
export function kpiAction(id: string): KpiAction {
  return id.startsWith('task:') ? { key: id.slice(5) } : { stop: id.replace(/^history:/, '') };
}

/**
 * Why the tasks that did not start did not start, as the data names it: an
 * input missing, an input that failed checks, an earlier task that failed.
 */
function notStartedCauses(outcomes: Iterable<TaskOutcome>): string[] {
  let missing = false;
  let checks = false;
  let earlier = false;
  for (const t of outcomes) {
    if (t.outcome !== 'not_started') continue;
    const last = t.attempts[t.attempts.length - 1];
    const ps = last?.stop === 'invalid_input' ? inputProblems(last.reason) : [];
    if (ps.some((p) => p.problem === 'missing')) missing = true;
    if (ps.some((p) => p.problem === 'checks')) checks = true;
    if (ps.some((p) => p.problem === 'failed') || (!ps.length && t.cause)) earlier = true;
  }
  return factList(earlier ? msg('Earlier task failed') : '', missing ? msg('Input missing') : '', checks ? msg('Input failed checks') : '');
}

/** The history filtered by `stop`, named `label`. */
const history = (stop: string, label: string): StatTile['action'] => ({ id: `history:${stop}`, label });

/** The one task behind a count, by key and name; undefined when there are several. */
function onlyTask(journal: readonly JournalRow[], keys: readonly string[]): { key: string; name: string } | undefined {
  const only = keys.length === 1 ? keys[0] : undefined;
  if (!only) return undefined;
  const row = journal.find((r) => r.key === only);
  return { key: only, name: row ? kindUnit(row) : only };
}

/** The tasks behind a count: the task itself when it is one (named), else the history filtered to them (`label`). */
function show(journal: readonly JournalRow[], keys: readonly string[], stop: string, label: string): StatTile['action'] {
  const one = onlyTask(journal, keys);
  return one ? { id: `task:${one.key}`, label: one.name } : history(stop, label);
}

/**
 * The line under a count of events: the one task they belong to by name, else the
 * count of tasks (`many`) when it differs from the count of events; none at 0.
 */
function tasksLine(journal: readonly JournalRow[], count: number, keys: readonly string[], many: (n: number) => string): string[][] {
  if (!count) return [];
  const one = onlyTask(journal, keys);
  if (one) return [[one.name]];
  return keys.length === count ? [] : [[many(keys.length)]];
}

/**
 * The tiles: tasks (with `d` from the plan; from the journal alone otherwise),
 * attempts, cost and tokens (when reported), failed attempts, not started,
 * agent time, retries, corrections and model switches. Neutral by default:
 * only a problem count above 0 takes its tone (`problemTone`). A tile's lines
 * add facts the value does not give: a 0 has none. `highestCost: false` leaves
 * the kind with the highest cost out of the cost tile.
 */
export function kpiTiles(journal: readonly JournalRow[], d: Pick<RunDerived, 'outcomes' | 'counts'>, opts: { highestCost?: boolean } = {}): StatTile[] {
  const k = kpis(journal);
  const { outcomes, counts: c } = d;
  // The total is neutral; the parts that are problems carry their own status.
  const parts: Fact[] = [
    { text: stateCount('done', c.doneTotal), tone: 'neutral' },
    { text: c.skipped ? stateCount('skipped', c.skipped) : '', tone: 'neutral' },
    { text: c.failed ? stateCount('failed', c.failed) : '', tone: problemTone(c.failed, 'failed') },
    { text: c.not_started ? stateCount('not_started', c.not_started) : '', tone: problemTone(c.not_started, 'attention') },
    { text: c.partial ? stateCount('partial', c.partial) : '', tone: problemTone(c.partial, 'attention') },
    { text: c.cancelled ? stateCount('cancelled', c.cancelled) : '', tone: 'neutral' },
  ];
  return [
    { id: 'tasks', label: msg('Tasks', { id: 'tasks', desc: 'A count of tasks' }), value: c.total, sub: [parts] },
    {
      id: 'attempts',
      label: msg('Attempts'),
      value: k.attempts,
      sub: [factList(k.launches === 1 ? msg('1 agent session') : msg(str`${k.launches} agent sessions`), k.python === 1 ? msg('1 Python task attempt') : msg(str`${k.python} Python task attempts`))],
      tip: msg('Attempts that ran, retries included (journal.jsonl)'),
    },
    ...spendTiles(journal, opts.highestCost ?? true),
    {
      id: 'bad',
      tone: problemTone(k.bad, 'failed'),
      label: msg('Failed attempts'),
      value: k.bad,
      sub: [],
      ...(k.bad ? { action: history('bad', msg('Failed attempts in history')) } : {}),
    },
    {
      id: 'notstarted',
      tone: problemTone(c.not_started, 'attention'),
      label: msg('Not started'),
      value: c.not_started,
      sub: c.not_started ? [notStartedCauses(outcomes.values())] : [],
      ...(c.not_started ? { action: history('invalid_input', msg('Tasks not started in history')) } : {}),
    },
    {
      id: 'wall',
      label: msg('Agent session time'),
      value: fmtDur(k.launchWall),
      sub: [[msg(str`Python tasks: ${fmtDur(k.pythonWall)}`)]],
      tip: msg('Summed over agent sessions, including sessions that ran at once'),
    },
    {
      id: 'retry',
      label: msg('Retries'),
      value: k.retries,
      sub: tasksLine(journal, k.retries, k.retriedKeys, (n) => msg(str`${n} tasks retried`)),
      tip: retryTip(),
      ...(k.retries ? { action: show(journal, k.retriedKeys, 'retried', msg('Retried tasks in history')) } : {}),
    },
    {
      id: 'ct',
      label: msg('Corrections'),
      value: k.fixups,
      sub: tasksLine(journal, k.fixups, k.fixupKeys, (n) => msg(str`${n} tasks with corrections`)),
      tip: correctionTip(),
      ...(k.fixups ? { action: show(journal, k.fixupKeys, 'fixup', msg('Attempts with corrections in history')) } : {}),
    },
    {
      id: 'fo',
      label: msg('Model switches'),
      value: k.switches,
      sub: tasksLine(journal, k.switches, k.switchKeys, (n) => msg(str`${n} tasks with model switches`)),
      tip: modelSwitchTip(),
    },
  ];
}

/** Cost and tokens, when any attempt reported them; the cost tile names the kind with the highest cost when `highest`. */
function spendTiles(journal: readonly JournalRow[], highest: boolean): StatTile[] {
  const s = spendOf(journal);
  if (!s) return [];
  const top = spendByKind(journal)[0];
  return [
    {
      id: 'cost',
      label: msg('Cost'),
      value: usd(s.cost),
      sub: highest && top && top.share !== null ? [[msg(str`Highest cost: ${top.kind}`)], factList(usd(top.spend.cost), msg(str`${Math.round(top.share * 100)}% of the total`))] : [[]],
      tip: msg('Reported by the coding agent'),
    },
    {
      id: 'tokens',
      label: msg('Tokens'),
      value: tokenCount(totalTokens(s)),
      sub: [factList(msg(str`${tokenCount(s.input)} input`), msg(str`${tokenCount(s.output)} output`), msg(str`${tokenCount(s.cache_read + s.cache_creation)} cache`))],
      tip: facts(
        msg(str`${tokenCount(s.cache_read)} cache read`),
        msg(str`${tokenCount(s.cache_creation)} cache write`),
        s.calls === 1 ? msg('1 API call') : msg(str`${s.calls} API calls`),
      ),
    },
  ];
}
