// What a task reads, file by file, and the earlier tasks it waits for: the
// Input tab's arithmetic, apart from its templates. Pure.
import type { ContractSpec, TaskIO, UpstreamTask } from '@contraagent/api';

/** One file the task reads: its input contract, and the earlier task that writes it (with that task's output contract), if any. */
export interface InputFile {
  spec: ContractSpec;
  from: UpstreamTask | null;
  /** The earlier task's contract for the same file: whether it was written and passed its checks. */
  out: ContractSpec | null;
}

/** One earlier task: how many of its output files this task reads, and the others. */
export interface EarlierTask {
  task: UpstreamTask;
  read: number;
  /** Its output files this task does not read. */
  rest: ContractSpec[];
}

/** An output file that is missing, or did not pass its checks. */
export const notPassed = (o: ContractSpec): boolean => !o.file.exists || (o.status != null && o.status !== 'valid');

/**
 * The Input tab of a task: every file it reads (its declared inputs), each with the
 * earlier task that writes it; then the earlier tasks it waits for, each with the
 * output files it does not read. An earlier task with an output that is missing or did
 * not pass comes first.
 */
export function inputView(io: Pick<TaskIO, 'inputs' | 'upstream'>): { files: InputFile[]; earlier: EarlierTask[] } {
  const reads = new Set(io.inputs.map((o) => o.path));
  const files = io.inputs.map((spec): InputFile => {
    for (const u of io.upstream) {
      const out = u.outputs.find((o) => o.path === spec.path);
      if (out) return { spec, from: u, out };
    }
    return { spec, from: null, out: null };
  });
  const earlier = io.upstream.map((task): EarlierTask => ({
    task,
    read: task.outputs.filter((o) => reads.has(o.path)).length,
    rest: task.outputs.filter((o) => !reads.has(o.path)),
  }));
  const bad = (e: EarlierTask) => Number(e.task.outputs.some(notPassed));
  return { files, earlier: [...earlier].sort((a, b) => bad(b) - bad(a)) };
}
