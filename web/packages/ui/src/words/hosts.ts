// Words for the hosts behind a hub's runs (`Info.hosts`): a host's state, its
// last report, its runs, and a run whose host stopped reporting. The code's
// terms (`up`, `last_seen`, `unresponsive`) stay in the data and in tooltips.
import type { HostSummary, RunActivity } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, localTime } from './format.js';

/** A run whose host stopped reporting (`RunSummary.unresponsive`), as a status value. */
export const noReportLabel = (): string => msg('no report from host');

/** A run's process as a status value: `running`, `no report from host`; '' for a run that is not running. */
export function activityLabel(a: RunActivity): string {
  return a === 'running' ? msg('running') : a === 'unresponsive' ? noReportLabel() : '';
}

/** A host's state: `up`, or `no report` (its reports stopped, or it never reported). */
export const hostStateLabel = (h: Pick<HostSummary, 'up'>): string =>
  h.up ? msg('up', { desc: 'A host whose reports keep arriving' }) : msg('no report');

/** A host's state with the time of its last report where one is known: `no report since Oct 13, 10:41:03`. */
export const hostStateSince = (h: Pick<HostSummary, 'up' | 'last_seen'>): string =>
  !h.up && h.last_seen ? msg(str`no report since ${localTime(h.last_seen, true)}`) : hostStateLabel(h);

/** When a host last reported: `Last report Oct 13, 10:41:03`; '' when it never did. */
export const lastReport = (h: Pick<HostSummary, 'last_seen'> | undefined): string =>
  h?.last_seen ? msg(str`Last report ${localTime(h.last_seen, true)}`) : '';

/** A host's id as a fact: `Host h1`; for a run whose run.json names none, `No host id`. */
export const hostFact = (id: string): string => (id ? msg(str`Host ${id}`) : msg('No host id'));

/** How many runs: `1 run`, `4 runs`. */
export const runCount = (n: number): string => (n === 1 ? msg('1 run') : msg(str`${n} runs`));

/** How many runs have no report from their host: `1 with no report from host`. */
export const noReportCount = (n: number): string => msg(str`${n} with no report from host`);

/** The hosts in one line: `2 hosts | 1 with no report`. */
export function hostsLine(hosts: readonly Pick<HostSummary, 'up'>[]): string {
  const quiet = hosts.filter((h) => !h.up).length;
  return facts(hosts.length === 1 ? msg('1 host') : msg(str`${hosts.length} hosts`), quiet ? msg(str`${quiet} with no report`) : '');
}

/** Seconds between a host's reports; '—' when it does not report. */
export const reportInterval = (s: number | null | undefined): string => (s == null ? '—' : fmtDur(s));
