// @vitest-environment happy-dom
// Each account's usage with the run's caps beside it, whether it is paused now, and its rests.
import type { CredentialRest, JournalRow } from '@contraagent/api';
import { afterEach, describe, expect, it } from 'vitest';
import type { CaQuota } from './ca-quota.js';
import './ca-quota.js';

const reading = (credential: string, five: number) => ({
  observed_at: '2026-10-14T00:00:00+00:00',
  credential,
  five_hour_pct: five,
  five_hour_resets_at: '2026-10-14T04:30:00+00:00',
  seven_day_pct: 11,
  seven_day_resets_at: '2026-10-15T08:00:00+00:00',
  status: 'allowed',
});
const row = (credential: string, five: number): JournalRow => ({
  ts: '2026-10-14T00:00:05+00:00',
  key: `t-${credential}`,
  kind: 't',
  stop: 'completed',
  ok: true,
  quota: [reading(credential, five)],
});
const rest = (credential: string, ended = ''): CredentialRest => ({
  credential,
  window: 'five_hour',
  pct: 93,
  cap: 90,
  rule: '',
  until: '2099-01-01T00:00:00+00:00', // the window resets later than any test runs
  since: '2026-10-14T00:00:06+00:00',
  ended,
});

async function quota(props: Partial<Pick<CaQuota, 'journal' | 'caps' | 'rests' | 'rule' | 'live'>>): Promise<ShadowRoot> {
  const el = document.createElement('ca-quota');
  Object.assign(el, props);
  document.body.append(el);
  await el.updateComplete;
  return el.shadowRoot!;
}

afterEach(() => document.body.replaceChildren());

describe('ca-quota', () => {
  it('shows a cap on its window and a paused account', async () => {
    const root = await quota({
      journal: [row('personal', 93)],
      caps: [{ credential: 'personal', five_hour_pct: 90, seven_day_pct: 95 }],
      rests: [rest('personal')],
      rule: 'flows.usage_pace',
    });
    const text = root.textContent ?? '';
    expect(text).toContain('Limits: weekly 95% | 5-hour 90%');
    expect(text).toContain('| limit 90%');
    expect(text).toContain('paused until');
    expect(text).toContain('Usage rule');
    expect(text).toContain('flows.usage_pace');
    expect(root.querySelectorAll('.bar .cap').length).toBe(2);
    expect(root.querySelectorAll('.rests li').length).toBe(1);
  });

  it('shows an account paused by an earlier run’s reading, and no pill once its rest ended', async () => {
    const root = await quota({ journal: [row('other', 10)], rests: [rest('personal', '2026-10-14T00:10:00+00:00')] });
    const heads = [...root.querySelectorAll('.acct-h')].map((h) => h.textContent ?? '');
    expect(heads.some((h) => h.includes('personal'))).toBe(true);
    expect(root.textContent).not.toContain('paused until');
    expect(root.querySelector('.rests li')?.textContent).toContain('→');
  });

  it('shows no pill once the window reset, nor for a rule’s rest after the run', async () => {
    const reset = { ...rest('personal'), until: '2020-01-01T00:00:00+00:00' };
    const ruled = { ...rest('personal'), window: '' as const, pct: null, cap: null, rule: 'over the pace', until: '' };
    expect((await quota({ journal: [row('personal', 93)], rests: [reset] })).textContent).not.toContain('paused');
    document.body.replaceChildren();
    expect((await quota({ journal: [row('personal', 93)], rests: [ruled] })).querySelector('.acct-h')?.textContent).not.toContain('paused');
    document.body.replaceChildren();
    expect((await quota({ journal: [row('personal', 93)], rests: [ruled], live: true })).querySelector('.acct-h')?.textContent).toContain(
      'paused',
    );
  });

  it('writes a cap as configured', async () => {
    const root = await quota({ journal: [row('personal', 3)], caps: [{ credential: 'personal', five_hour_pct: 0.5 }] });
    expect(root.textContent).toContain('limit 0.5%');
    expect(root.textContent).toContain('Limits: 5-hour 0.5%');
  });
});
