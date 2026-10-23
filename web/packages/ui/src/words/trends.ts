// Words for the trends: what the runs of a period add up to (`/api/trends`).
import { msg, str } from '@lit/localize';
import { getLocale } from '../core/i18n.js';

/** The trends page's name: in the run picker, the page's heading and the browser tab. */
export const trendsTitle = (): string => msg('Trends');
/** What the trends page shows, for the run picker's entry and the page's tooltip. */
export const trendsTip = (): string => msg('Totals of the runs in a period');
/** The trends page's first tab: the trends, with the custom views that name no tab. */
export const trendsFirstTab = (): string => msg('Summary', { desc: "The trends page's first tab: what the runs of the period add up to, beside the tabs of the custom views" });

/** A day of the period (YYYY-MM-DD) with its month as a word: `Oct 14`. */
export function dayLabel(day: string, locale: string = getLocale()): string {
  const d = new Date(`${day}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) return day;
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(d);
}

/** The period in words: `Oct 1 to Oct 14, 2026`, and its time zone after it when given (`| Asia/Tokyo`: where no time zone control names it). */
export function periodLabel(from: string, to: string, tz = '', locale: string = getLocale()): string {
  const year = to.slice(0, 4);
  return tz
    ? msg(str`${dayLabel(from, locale)} to ${dayLabel(to, locale)}, ${year} | ${tz}`, { desc: 'The days the trends cover, and the time zone they are counted in' })
    : msg(str`${dayLabel(from, locale)} to ${dayLabel(to, locale)}, ${year}`, { desc: 'The days the trends cover' });
}

/** A length of period ending today: `7 days`. */
export const lastDays = (n: number): string => msg(str`${n} days`, { desc: 'A period of the trends: the last N days, today included' });
export const customPeriod = (): string => msg('Dates', { desc: 'A period of the trends from one chosen day to another' });
export const fromLabel = (): string => msg('From', { desc: 'The first day of the trends period' });
export const toLabel = (): string => msg('To', { desc: 'The last day of the trends period' });
export const zoneLabel = (): string => msg('Time zone');
export const groupLabel = (): string => msg('Run group');
export const allGroups = (): string => msg('All run groups');

/** Monday to Sunday, short, in the UI's language (the rows of the run starts' grid). */
export function weekdayLabels(locale: string = getLocale()): string[] {
  const f = new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' });
  // 2026-10-12 was a Monday.
  return Array.from({ length: 7 }, (_, i) => f.format(new Date(Date.UTC(2026, 9, 12 + i, 12))));
}

/** The headings and labels of the trends' sections. */
export const trendWords = () => ({
  runs: msg('Runs', { id: 'trends-runs', desc: 'How many runs worked in the trends period' }),
  attempts: msg('Attempts'),
  done: msg('Done'),
  cost: msg('Cost'),
  tokens: msg('Tokens'),
  time: msg('Time'),
  costByDay: msg('Cost by day'),
  costByDayTip: msg('Reported by the coding agent, on the day each attempt ended'),
  kinds: msg('Kinds'),
  kind: msg('Kind'),
  group: msg('Group'),
  tasks: msg('Tasks'),
  tasksDone: msg('Tasks done'),
  partial: msg('Partly done', { id: 'trends-partial', desc: 'A column: tasks or attempts whose output is a placeholder (partial)' }),
  medianTime: msg('Median time'),
  totalTime: msg('Total time'),
  models: msg('Models'),
  model: msg('Model'),
  sessions: msg('Agent sessions'),
  calls: msg('API calls'),
  input: msg('Input'),
  output: msg('Output'),
  cacheRead: msg('Cache read'),
  cacheWrite: msg('Cache write'),
  outcomes: msg('Attempts not done'),
  outcome: msg('Outcome'),
  denials: msg('Denied tool calls'),
  toolCalls: msg('Tool calls'),
  pythonKinds: msg('Python tasks'),
  tool: msg('Tool'),
  usage: msg('Subscription usage'),
  usageTip: msg('The highest reading of each day'),
  deferred: msg('Not run'),
  cause: msg('Cause'),
  task: msg('Task'),
  when: msg('When'),
  rests: msg('Paused identities'),
  identity: msg('Identity'),
  event: msg('Event'),
  starts: msg('Run starts', { desc: 'How many runs started, by weekday and hour' }),
  startsTip: msg('By weekday and hour, in the period\'s time zone'),
  run: msg('Run'),
  started: msg('Started'),
  trendPanels: msg('Custom views'),
});

/** A count beside a title: `Not run | 64`. */
export const titled = (title: string, n: number): string => `${title} | ${n}`;

/** A deferral by a paused identity, the identity named when the run's sentence names it (`personal rests: ...`). */
export const pausedCause = (reason: string): string => {
  const who = /^(\S+) rests\b/.exec(reason)?.[1];
  return who ? msg(str`Identity ${who} paused`) : msg('Identity paused');
};

/** A model's name with its coding agent: `sonnet | claude`. */
export const modelName = (agent: string, model: string): string => (agent ? `${model || '—'} | ${agent}` : model || '—');

/** An identity's window in a line's name: `personal | weekly`. */
export const usageLine = (identity: string, window: string): string => `${identity} | ${window}`;

/** A rest's start or end, in words. */
export const restEvent = (event: string | null | undefined): string =>
  event === 'end' ? msg('ended', { desc: 'A paused identity was used again' }) : event === 'start' ? msg('started', { desc: 'An identity began its pause' }) : event || '—';

/** A day's share of an amount: `$1.20 a day`. */
export const perDay = (amount: string): string => msg(str`${amount} a day`, { desc: 'An average over the days of the trends period that had any cost' });

/** The share of attempts done: `Done 97%`. */
export const doneShare = (pctText: string): string => msg(str`Done ${pctText}`);

/** The trends' empty state. */
export const noRunsInPeriod = (): string => msg('No runs in this period');

/** The period of an export, which a page cannot change. */
export const exportedPeriod = (): string => msg('Period of this export');
