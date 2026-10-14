// @vitest-environment happy-dom
import type { Hosts } from '@contraagent/api';
import { afterEach, describe, expect, it } from 'vitest';
import './ca-hosts.js';

const later = new Date(Date.now() + 2 * 3600_000).toISOString();
const reading = { observed_at: '2026-10-14T00:00:00+00:00', credential: 'personal', five_hour_pct: 93, seven_day_pct: 40, status: '' };

afterEach(() => document.body.replaceChildren());

describe('ca-hosts', () => {
  it('shows an account paused now, as the overview does', async () => {
    const hosts = {
      hosts: [{ host_id: 'h1', up: true, last_seen: '2026-10-14T00:00:00+00:00', interval_s: 15, runs: 1, running: 1, unresponsive: 0 }],
      quota: [
        {
          credential: 'personal',
          account: '',
          first: reading,
          last: reading,
          rests: [{ credential: 'personal', window: 'five_hour', pct: 93, cap: 90, rule: '', until: later, account: '', since: '2026-10-14T00:00:00+00:00', ended: '' }],
        },
      ],
    } as unknown as Hosts;
    const el = document.createElement('ca-hosts');
    Object.assign(el, { hosts });
    document.body.append(el);
    await el.updateComplete;
    const quota = el.shadowRoot!.querySelector('ca-quota')!;
    await quota.updateComplete;
    expect(quota.rests).toHaveLength(1);
    expect(quota.shadowRoot!.textContent).toContain('paused until');
  });
});
