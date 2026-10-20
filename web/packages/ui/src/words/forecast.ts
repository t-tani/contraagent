// The forecast (`Forecast`): the tasks a run is expected to create and has not yet,
// from the run of its flow that finished last before it.
import type { Forecast } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, listText, usd } from './format.js';

/** A kind node's expected tasks: "+3", and its words. */
export function expectedPill(n: number): { text: string; label: string } {
  return { text: msg(str`+${n}`), label: n === 1 ? msg('1 more task expected (forecast)') : msg(str`${n} more tasks expected (forecast)`) };
}

/** The forecast in one line: "Forecast: 7 more tasks | 46s of task time | $0.60". */
export function forecastLine(f: Forecast): string {
  return facts(
    f.remaining === 1 ? msg('Forecast: 1 more task') : msg(str`Forecast: ${f.remaining} more tasks`),
    f.wall_s ? msg(str`${fmtDur(f.wall_s)} of task time`) : '',
    f.cost_usd !== null && f.cost_usd !== undefined ? usd(f.cost_usd) : '',
  );
}

/** Where the forecast comes from, as its tooltip. */
export const forecastTip = (f: Forecast): string =>
  msg(str`Tasks this run is expected to create and has not yet, from the run ${f.earlier_run} of the same flow (forecast)`);

/** The groups the plan has no task of yet, with how many each is expected to have: "Not in the plan yet: review +3, report +1". */
export function notInPlanLine(items: readonly { group: string; remaining: number }[]): string {
  return items.length ? msg(str`Not in the plan yet: ${listText(items.map((x) => `${x.group} +${x.remaining}`))}`) : '';
}
