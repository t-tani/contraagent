// Why a task waits or did not start, as a phrase that names the cause the data
// has: the earlier task, the input and what happened to the task that writes it.
import { inputProblems, isFinished, runRelative, type InputProblem, type Outcome, type TaskOutcome } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { kindUnit } from './format.js';

/**
 * Why a waiting task has not run, as a phrase that starts in lower case: the
 * earlier task it waits for (`waits for output of review · zeta`), or how many
 * (`waits for output of 3 earlier tasks`); '' for none.
 */
export function waitCause(waits: readonly { kind?: string | null; unit?: string | null }[]): string {
  const first = waits[0];
  if (!first) return '';
  return waits.length === 1 ? msg(str`waits for output of ${kindUnit(first)}`) : msg(str`waits for output of ${waits.length} earlier tasks`);
}

/** The task that writes an input, as far as the run knows it. */
export interface InputSource {
  /** `kind · unit`. */
  name: string;
  /** What happened to it, when known. */
  outcome?: Outcome | undefined;
}

/**
 * Why an input stopped a task, in one phrase that starts in lower case:
 * `input out/review/zeta.json is missing because review · zeta failed`,
 * `input out/a.json failed checks`, `input out/review/zeta.json is the output of
 * failed task review · zeta`. `path` is already shown run-relative.
 */
export function inputCause(path: string, problem: InputProblem['problem'], from?: InputSource): string {
  if (problem === 'failed')
    return from ? msg(str`input ${path} is the output of failed task ${from.name}`) : msg(str`input ${path} is the output of a failed task`);
  if (problem === 'checks') return from ? msg(str`input ${path} from ${from.name} failed checks`) : msg(str`input ${path} failed checks`);
  if (!from) return msg(str`input ${path} is missing`);
  if (from.outcome === 'failed') return msg(str`input ${path} is missing because ${from.name} failed`);
  if (from.outcome === 'not_started') return msg(str`input ${path} is missing because ${from.name} did not start`);
  if (from.outcome && isFinished(from.outcome))
    return msg(str`input ${path} from ${from.name} is missing`);
  return msg(str`input ${path} is missing because ${from.name} did not finish`);
}

/**
 * Why a task did not start, as a phrase after "Not started: ": the input its
 * refusal names and why that input is not ready (`input out/review/zeta.json is
 * missing because review · zeta failed`), or the earlier task that failed and
 * stopped it (`earlier task review · zeta failed`); '' when the run does not tell.
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
  return c ? msg(str`earlier task ${kindUnit(c)} failed`) : '';
}
