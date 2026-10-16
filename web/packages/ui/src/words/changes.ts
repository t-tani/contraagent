// Words for a task's changes: the files an attempt created, modified or deleted under
// the patterns its task declares (`changes` in a journal row).
import { msg, str } from '@lit/localize';

/** What happened to one file in one attempt. `removed`: it created the file, and the file was removed because the attempt failed; `kept`: it created the file, and the file stayed though the attempt failed (`keep_failed_changes`). */
export type ChangeKind = 'created' | 'modified' | 'deleted' | 'removed' | 'kept';

/** `1 changed file`, `3 changed files`. */
export const changedFiles = (n: number): string => (n === 1 ? msg('1 changed file') : msg(str`${n} changed files`));

/** What a task's changed files are, for a tooltip. */
export const changedFilesTip = (): string =>
  msg("Files under the task's declared patterns that its attempts created, modified or deleted (changes)");

/** What happened to a file, in words. */
export function changeLabel(kind: ChangeKind): string {
  switch (kind) {
    case 'created':
      return msg('created');
    case 'modified':
      return msg('modified');
    case 'deleted':
      return msg('deleted');
    case 'removed':
      return msg('created, removed after the failed attempt');
    case 'kept':
      return msg('created, kept after the failed attempt');
  }
}
