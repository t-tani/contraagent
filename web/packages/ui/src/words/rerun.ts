// Why a resume ran a task again (`JournalRow.rerun`): the parts of its fingerprint that
// changed, read from `fingerprint_parts`, and a divergence.
import type { JournalRow } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, listText } from './format.js';

/** What a journal row says about a rerun: the parts of the fingerprint that changed since the row before, and whether it is a divergence. */
export interface Rerun {
  /** The reason as the journal records it. */
  text: string;
  /** The fingerprint's parts whose digest differs from the earlier row's (`definition`, `params`, ...), in the row's order. */
  changed: string[];
  /** The flow gave other params for the same outputs (`divergence: ...`). */
  divergence: boolean;
}

/**
 * The rerun of `rows[i]` (one task's journal rows, in journal order), or null when the
 * row is no rerun: its `rerun`, the parts of `fingerprint_parts` that differ from the
 * latest earlier row that has them, and whether the reason is a divergence.
 */
export function rerunOf(rows: readonly JournalRow[], i: number): Rerun | null {
  const row = rows[i];
  if (!row?.rerun) return null;
  const now = row.fingerprint_parts ?? {};
  const before = rows.slice(0, i).reverse().find((r) => Object.keys(r.fingerprint_parts ?? {}).length)?.fingerprint_parts ?? {};
  const changed = Object.keys(now).length && Object.keys(before).length ? [...new Set([...Object.keys(now), ...Object.keys(before)])].filter((k) => now[k] !== before[k]) : [];
  return { text: row.rerun, changed, divergence: row.rerun.startsWith('divergence') };
}

/** A part of a fingerprint (`fingerprint_parts`) in words; one these words do not know, as it is recorded. */
export function fingerprintPartWord(part: string): string {
  switch (part) {
    case 'definition':
      return msg('definition', { id: 'part-definition', desc: 'A part of what defines a task: its instructions, role, schemas, validators or source' });
    case 'params':
      return msg('params', { id: 'part-params', desc: 'A part of what defines a task: what it was given (params)' });
    case 'outside':
      return msg('outside state');
    case 'output_of':
      return msg('the file it fills in');
    case 'input_files':
      return msg('input files', { id: 'part-input-files', desc: 'A part of what defines a task: the files given to it by path and hash' });
    default:
      return part;
  }
}

/** The word for a divergence, and its tooltip. */
export const divergenceWord = (): string => msg('divergence');
export const divergenceTip = (): string =>
  msg('The flow gave other params for the same outputs of the tasks before it (divergence): a clock, randomness, outside state or changed flow code');

/** A rerun in one line: "Ran again after a resume | divergence | Changed: params"; the recorded reason when no part is known to have changed. */
export function rerunLine(r: Rerun): string {
  return facts(
    msg('Ran again after a resume'),
    r.divergence ? divergenceWord() : '',
    r.changed.length ? msg(str`Changed: ${listText(r.changed.map(fingerprintPartWord))}`) : r.divergence ? '' : r.text,
  );
}
