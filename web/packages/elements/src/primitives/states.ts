// States and their looks: a state is an id the host chooses; `StateStyles` maps it
// to a word, a tone and a shape, and orders the states (the legend's order).
import type { Tone } from '../core/tone.js';
import type { MarkShape } from './legend.js';

export interface StateStyle {
  /** The word beside a mark and in the legend. */
  label: string;
  tone: Tone;
  shape: MarkShape;
  /** Higher is more severe: what a mark standing for several items shows. */
  rank: number;
  /** How many items are in this state, number first ("3 failed"); default: the number and `label`. */
  count?: (n: number) => string;
}

/** State id → look. The key order is the legend order. */
export type StateStyles = Readonly<Record<string, StateStyle>>;

/** The most severe of `states` by `styles` (an unknown state ranks lowest); '' for none. */
export function worstState(states: Iterable<string>, styles: StateStyles): string {
  let worst = '';
  for (const s of states) if (worst === '' || (styles[s]?.rank ?? -Infinity) > (styles[worst]?.rank ?? -Infinity)) worst = s;
  return worst;
}

/** How many items are in state `s`, in words. */
export const stateCount = (styles: StateStyles, s: string, n: number): string => styles[s]?.count?.(n) ?? `${n} ${styles[s]?.label ?? s}`;
