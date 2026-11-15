// @vitest-environment happy-dom
// The shared clock: a tick a second for its hosts, and none drawn while the page is hidden.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ClockController, pageHidden } from './clock.js';

const host = () => {
  const h = { updates: 0, addController: () => {}, removeController: () => {}, requestUpdate: () => void h.updates++, updateComplete: Promise.resolve(true) };
  return h;
};

describe('the shared clock', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('asks its host to draw each second, and not while the page is hidden', () => {
    vi.useFakeTimers();
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    const onDoc = vi.spyOn(document, 'addEventListener');
    const h = host();
    const clock = new ClockController(h);
    clock.hostConnected();
    vi.advanceTimersByTime(2000);
    expect(h.updates).toBe(2);
    hidden.mockReturnValue(true);
    expect(pageHidden()).toBe(true);
    vi.advanceTimersByTime(3000);
    expect(h.updates).toBe(2);
    // Shown again: the next tick draws.
    hidden.mockReturnValue(false);
    vi.advanceTimersByTime(1000);
    expect(h.updates).toBe(3);
    // It asks the page at each tick: no listener on the document of a page that embeds an element.
    expect(onDoc).not.toHaveBeenCalled();
    clock.hostDisconnected();
    vi.advanceTimersByTime(2000);
    expect(h.updates).toBe(3);
  });
});
