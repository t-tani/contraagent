// A flow call's own deadline (`time_box`), in words: the function node of the
// pipeline graph and its flow calls show it.
import type { TimeBoxRecord } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, listText, localTime } from './format.js';

/** A deadline's terms: `45m 00s | finishing time 15m 00s | finishing kinds: lint_fixer, report`. */
export function timeBoxFacts(box: TimeBoxRecord): string {
  const kinds = box.finishing_kinds ?? [];
  return facts(
    fmtDur(box.deadline_s),
    box.grace_s && kinds.length ? msg(str`finishing time ${fmtDur(box.grace_s)}`) : '',
    kinds.length ? msg(str`finishing kinds: ${listText(kinds)}`) : '',
  );
}

/** When one flow call's deadline falls, as an absolute time: `10/14 11:16:00`. */
export const deadlineAtText = (iso: string): string => localTime(iso, true);

/** The tooltip of a deadline row: the term, in code. */
export const timeBoxTip = (): string => msg('A deadline of its own (time_box)');
