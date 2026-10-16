// A contract file's status and its causes, in words (the UI says "checked
// file"; AGENTS.md "Words the UI shows").
import { inputProblems, runRelative, type ContractSpec, type ContractStatus, type Outcome } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { inputCause } from './causes.js';
import { sentence } from './format.js';

/** A contract status in words, in the current locale. */
export function contractStatusLabel(s: ContractStatus): string {
  switch (s) {
    case 'valid':
      return msg('passed');
    case 'invalid':
      return msg('failed checks');
    case 'refused':
      return msg('not written (task not started)');
    case 'failed':
      return msg('not written (task failed)');
    case 'running':
      return msg('not written yet (task running)');
    case 'pending':
      return msg('not written yet (task waiting)');
  }
}

/** A fact a contract's status word does not say, for its tooltip; '' when the word says it all. */
export function contractStatusWhy(s: ContractStatus): string {
  return s === 'failed' ? msg('The task failed before it wrote a file that passes its checks') : '';
}

/** What a correction is, for tooltips. */
export const correctionTip = (): string => msg('Another round in the same agent session after failed checks (rounds)');

/** How many corrections a file took (`rounds` counts the first round too), in words; '' for none. */
export function correctionsLabel(rounds: number | null | undefined, passed: boolean): string {
  const n = (rounds ?? 1) - 1;
  if (n < 1) return '';
  if (passed) return n === 1 ? msg('after 1 correction') : msg(str`after ${n} corrections`);
  return n === 1 ? msg('1 correction') : msg(str`${n} corrections`);
}

/** Who writes a file, for naming the task an input should have come from. */
export interface Producer {
  /** "kind · unit" of the task that writes it. */
  name: string;
  /** The file exists now. */
  written: boolean;
  /** What happened to that task, when known. */
  outcome?: Outcome | undefined;
}

/**
 * Why a task never ran, in one line beside its status: the input it was refused
 * for (from its check errors) and, when known, the task that should have written it;
 * '' when the run records no input error.
 */
export function notRunText(o: ContractSpec, run: string, producerOf?: (path: string) => Producer | undefined): string {
  const errors = o.errors ?? [];
  const p = inputProblems(`invalid input: ${errors.map((e) => e.replace(/^invalid input:\s*/, '')).join('; ')}`)[0];
  if (!p) return errors[0] ? sentence(runRelative(errors[0], run)) : '';
  const from = producerOf?.(p.path);
  return sentence(inputCause(runRelative(p.path, run), p.problem, from));
}
