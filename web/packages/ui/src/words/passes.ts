// A loop's passes and the loop itself, in words.
import { msg, str } from '@lit/localize';

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
