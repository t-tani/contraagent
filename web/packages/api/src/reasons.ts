// What a journal row's `reason` says, read as data: the inputs a refusal names,
// and paths cut to the run directory. Pure; the words for them are the UI's.

/** One input a task was refused for, read from its `invalid input: ...` reason. */
export interface InputProblem {
  /** The file, as the reason gives it (absolute). */
  path: string;
  /** The key of the task that writes it, when the reason names one. */
  producer: string;
  /**
   * `missing`: the file is not there; `checks`: it is there and failed its checks;
   * `failed`: it is there, written by a task that did not succeed (`producer`).
   */
  problem: 'missing' | 'checks' | 'failed';
}

/**
 * The inputs a refused task's reason names (`invalid input: input from <key> is
 * missing: <path>`, `invalid input: input from <key> ended <stop>: <path>`,
 * `invalid input: <path>: required input is missing`, `invalid input: <path>:
 * <check error>`), in order; [] for any other reason.
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
    x = /^input from (\S+) ended \S+: (\S+)/.exec(part);
    if (x) {
      out.push({ path: x[2] ?? '', producer: x[1] ?? '', problem: 'failed' });
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

/**
 * A text from the run (a failure reason) with absolute paths inside the run
 * directory cut to the part after `runs/<run>/`: `out/summarize/zeta.json`.
 */
export function runRelative(text: string | null | undefined, run: string): string {
  if (!text || !run) return text ?? '';
  const esc = run.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text.replace(new RegExp(`(?:/[^\\s:'"]*)?/${esc}/`, 'g'), '');
}
