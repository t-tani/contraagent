// The words the UI shows for run data, in the reader's terms. The code's own
// terms (stop values, plan states, round, hop, attempt ...) stay in the data and
// in tooltips; what the reader sees comes from here, so every screen says the
// same thing for the same state. The mapping is documented in AGENTS.md
// ("Words the UI shows").
import { isLaunched, type Hop, type JournalRow, type Outcome, type PlanNode, type TaskOutcome } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { fmtDur, kindUnit } from './format.js';

/** What happened to a task. */
export function outcomeLabel(o: Outcome): string {
  switch (o) {
    case 'done':
      return msg('done');
    case 'recovered':
      return msg('done after retrying');
    case 'failed':
      return msg('failed');
    case 'not_started':
      return msg('not started');
    case 'running':
      return msg('running');
    case 'waiting':
      return msg('waiting');
    case 'skipped':
      return msg('skipped');
  }
}

/**
 * A task's state: what the run says about it (`own`, from the journal and the
 * plan: a task with no attempt is `waiting` or, behind a failed task,
 * `not_started`), else what its own journal rows say.
 */
export function taskState(rows: readonly JournalRow[], own?: Pick<TaskOutcome, 'outcome'>): Outcome {
  if (own) return own.outcome;
  const last = rows[rows.length - 1];
  if (!last) return 'waiting';
  if (last.stop === 'invalid_input') return 'not_started';
  if (last.stop === 'skipped') return 'skipped';
  if (last.ok) return rows.some((r) => isLaunched(r) && !r.ok) ? 'recovered' : 'done';
  return 'failed';
}

/** A plan node's state (the task matrix, progress by kind). */
export function planStateLabel(s: PlanNode['state']): string {
  switch (s) {
    case 'done':
      return msg('done');
    case 'failed':
      return msg('failed');
    case 'blocked':
      return msg('not started');
    case 'running':
      return msg('running');
    case 'pending':
      return msg('waiting');
    case 'skipped':
      return msg('skipped');
  }
}

/** How one attempt ended (a journal row's `stop`), in words. Unknown values are shown as they are. */
export function stopLabel(stop: string | null | undefined): string {
  switch (stop) {
    case 'completed':
      return msg('done');
    case 'skipped':
      return msg('skipped');
    case 'invalid_input':
      return msg('not started: input not ready');
    case 'invalid_output':
      return msg('failed checks');
    case 'timeout':
      return msg('timed out');
    case 'max_turns':
      return msg('turn limit reached');
    case 'budget':
      return msg('cost limit reached');
    case 'context_budget':
      return msg('context limit reached');
    case 'stalled':
      return msg('stalled (no output)');
    case 'auth_failed':
      return msg('authentication failed');
    case 'api_error':
      return msg('API error');
    case 'rate_limited':
      return msg('rate limited');
    case 'refused':
      return msg('refused by the model');
    case 'aborted':
      return msg('aborted');
    case 'denied':
      return msg('permission denied');
    case 'error':
      return msg('error');
    case 'no_output':
      return msg('ended without a result');
    case 'launch_failed':
      return msg('could not start the agent');
    case 'credential_mismatch':
      return msg('wrong identity used');
    case null:
    case undefined:
    case '':
      return '—';
    default:
      return msg(str`unknown (${stop})`);
  }
}

/** The attempt as the reader counts it: "Attempt 1", "Attempt 2" ... (`JournalRow.attempt` is 0-based). */
export const attemptLabel = (attempt: number | null | undefined): string => msg(str`Attempt ${(attempt ?? 0) + 1}`);

/** A loop's pass (`flow[].loops[].pass`), as the reader counts it: "Pass 1", "Pass 2" ... (never an attempt). */
export const passLabel = (pass: number): string => msg(str`Pass ${pass}`);

/** A loop box's pass count: "1 pass", "up to 3 passes" (its loop's last pass). */
export const passCount = (n: number): string => (n <= 1 ? msg('1 pass') : msg(str`up to ${n} passes`));

/** How many passes a unit ran: "1 pass", "3 passes". */
export const passesRan = (n: number): string => (n <= 1 ? msg('1 pass') : msg(str`${n} passes`));

/** How many units ran each number of passes of a loop: "1 pass: 4 | 2 passes: 1". */
export const passSpread = (spread: readonly (readonly [number, number])[]): string =>
  spread.map(([n, units]) => (n <= 1 ? msg(str`1 pass: ${units}`) : msg(str`${n} passes: ${units}`))).join(' | ');

/** A loop of the flow (a loop box, a breadcrumb level). */
export const loopLabel = (): string => msg('loop');

/** `1 correction`, `3 corrections`; '' for none. */
export function correctionsText(n: number): string {
  if (n <= 0) return '';
  return n === 1 ? msg('1 correction') : msg(str`${n} corrections`);
}

/** A credential as the reader knows it: the built-in `ambient` shows as "default". */
export const credentialLabel = (c: string | null | undefined): string => (!c ? '' : c === 'ambient' ? msg('default') : c);

/** What a credential's label leaves out, for its tooltip: the built-in `ambient` is the local credentials. */
export const credentialTip = (c: string | null | undefined): string => (c === 'ambient' ? msg('local credentials (ambient)') : '');

/** One hop's model, or its route when the journal names no model. */
const hopModel = (h: Pick<Hop, 'model' | 'route'>): string => h.model || h.route || '—';

/**
 * A model switch in words, the one form every view uses:
 * `primary-model (rate limited) → fallback-model`; '' for a single hop.
 * With `time`, the attempt's time follows: `... → fallback-model | 0.2s`.
 */
export function modelSwitch(hops: readonly Hop[] | null | undefined, time?: number | null): string {
  if (!hops || hops.length < 2) return '';
  const steps = hops.map((h, i) => (i < hops.length - 1 ? msg(str`${hopModel(h)} (${stopLabel(h.stop)})`) : hopModel(h)));
  const chain = steps.join(' → ');
  return time === undefined || time === null ? chain : `${chain} | ${fmtDur(time)}`;
}

/** One input a task was refused for, read from its `invalid input: ...` reason. */
export interface InputProblem {
  /** The file, as the reason gives it (absolute). */
  path: string;
  /** The key of the task that writes it, when the reason names one. */
  producer: string;
  /** `missing`: the file is not there; `checks`: it is there and failed its checks. */
  problem: 'missing' | 'checks';
}

/**
 * The inputs a refused task's reason names (`invalid input: input from <key> is
 * missing: <path>`, `invalid input: <path>: required input is missing`,
 * `invalid input: <path>: <check error>`), in order; [] for any other reason.
 */
export function inputProblems(reason: string | null | undefined): InputProblem[] {
  const m = /^invalid input:\s*(.*)$/s.exec(reason || '');
  if (!m) return [];
  const out: InputProblem[] = [];
  for (const part of (m[1] ?? '').split('; ')) {
    let x = /^input from (\S+) is missing: (\S+)/.exec(part);
    if (x) {
      out.push({ path: x[2] ?? '', producer: x[1] ?? '', problem: 'missing' });
      continue;
    }
    x = /^(\S+?): required input is missing/.exec(part);
    if (x) {
      out.push({ path: x[1] ?? '', producer: '', problem: 'missing' });
      continue;
    }
    x = /^(\S+?): /.exec(part);
    if (x && !out.some((o) => o.path === x?.[1])) out.push({ path: x[1] ?? '', producer: '', problem: 'checks' });
  }
  return out;
}

/** The task that writes an input, as far as the run knows it. */
export interface InputSource {
  /** `kind · unit`. */
  name: string;
  /** What happened to it, when known. */
  outcome?: Outcome | undefined;
}

/**
 * Why an input was not ready, in one phrase that starts in lower case:
 * `input out/review/zeta.json is missing because review · zeta failed`,
 * `input out/a.json failed checks`. `path` is already shown run-relative.
 */
export function inputCause(path: string, problem: InputProblem['problem'], from?: InputSource): string {
  if (problem === 'checks') return from ? msg(str`input ${path} from ${from.name} failed checks`) : msg(str`input ${path} failed checks`);
  if (!from) return msg(str`input ${path} is missing`);
  if (from.outcome === 'failed') return msg(str`input ${path} is missing because ${from.name} failed`);
  if (from.outcome === 'not_started') return msg(str`input ${path} is missing because ${from.name} did not start`);
  if (from.outcome === 'done' || from.outcome === 'recovered' || from.outcome === 'skipped')
    return msg(str`input ${path} from ${from.name} is missing`);
  return msg(str`input ${path} is missing because ${from.name} did not finish`);
}

/**
 * Why a task did not start, as a phrase after "Not started: ": the input its
 * refusal names and why that input is not ready (`input out/review/zeta.json is
 * missing because review · zeta failed`), or the earlier task that failed and
 * stopped it (`review · zeta failed`); '' when the run does not tell.
 * `writerOf` names the task that writes a path, for a reason that names none.
 */
export function notStartedCause(
  t: Pick<TaskOutcome, 'attempts' | 'cause'>,
  outcomes: ReadonlyMap<string, TaskOutcome>,
  run: string,
  writerOf?: (path: string) => string | undefined,
): string {
  const last = t.attempts[t.attempts.length - 1];
  if (last?.stop === 'invalid_input') {
    const p = inputProblems(last.reason)[0];
    if (!p) return runRelative(last.reason, run);
    const key = p.producer || writerOf?.(p.path) || '';
    const w = key ? outcomes.get(key) : undefined;
    return inputCause(runRelative(p.path, run), p.problem, w ? { name: kindUnit(w), outcome: w.outcome } : undefined);
  }
  const c = t.cause ? outcomes.get(t.cause) : undefined;
  return c ? msg(str`${kindUnit(c)} failed`) : '';
}

/**
 * A text from the run (a failure reason) with absolute paths inside the run
 * directory cut to the part after `runs/<run>/`: `out/summarize/zeta.json`.
 */
export function runRelative(text: string | null | undefined, run: string): string {
  if (!text || !run) return text ?? '';
  const esc = run.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text.replace(new RegExp(`(?:/[^\\s:'"]*)?/${esc}/`, 'g'), '');
}
