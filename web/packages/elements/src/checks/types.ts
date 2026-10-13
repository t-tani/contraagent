// What `<cae-check-table>` shows: a row per named value, what it must be, what
// it is, and the verdict.

/** A check's result: passed, failed, a warning, or no verdict (a word may still say why). */
export type Verdict = 'pass' | 'fail' | 'warn' | 'none';

export interface CheckRow {
  /** What is checked: a field's name. */
  name: string;
  /** What it must be: a type, in code; with `extra`, a phrase. */
  expected: string;
  /** It may be absent: "optional" follows `expected`. */
  optional?: boolean;
  /** Not one of the expected names: `expected` is a phrase, not code. */
  extra?: boolean;
  /** The value was found (`value`, possibly undefined or null); else "—". */
  hasValue: boolean;
  value?: unknown;
  verdict: Verdict;
  /** The verdict in words; '' with `none` for an empty cell. */
  verdictLabel: string;
  /** The verdict's tooltip. */
  tip?: string;
}

export interface CheckTableStrings {
  /** The header of the names. */
  name: string;
  expected: string;
  /** The header of the values. */
  actual: string;
  verdict: string;
  optional: string;
  /** A list's length. */
  items: (n: number) => string;
  /** An object's summary, before its first keys. */
  object: string;
}

export const DEFAULT_CHECK_TABLE_STRINGS: CheckTableStrings = {
  name: 'Name',
  expected: 'Expected',
  actual: 'Value',
  verdict: 'Check',
  optional: 'optional',
  items: (n) => (n === 1 ? '1 item' : `${n} items`),
  object: 'object',
};
