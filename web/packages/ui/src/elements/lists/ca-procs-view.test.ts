// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import './ca-procs-view.js';
import type { CaProcsView } from './ca-procs-view.js';

async function mount(props: Partial<CaProcsView>): Promise<CaProcsView> {
  const el = document.createElement('ca-procs-view');
  Object.assign(el, props);
  document.body.append(el);
  await el.updateComplete;
  return el;
}

describe('ca-procs-view', () => {
  it('with no live process: the run is not running', async () => {
    const el = await mount({});
    expect(el.shadowRoot?.textContent).toContain('No processes | run not running');
    el.remove();
  });

  it('in an export: the processes are not in it', async () => {
    const el = await mount({ exported: true });
    expect(el.shadowRoot?.textContent).toContain('No processes | not in this export');
    el.remove();
  });
});
