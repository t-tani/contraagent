// @vitest-environment happy-dom
// Where an element remembers: in the memory of the nearest root given one
// (across shadow roots), else in the page's history entry.
import { afterEach, describe, expect, it } from 'vitest';
import { LocalMemory, RememberedSet, keepMemory, memoryOf, pageMemory } from './memory.js';

afterEach(() => {
  document.body.replaceChildren();
  history.replaceState(null, '');
});

/** A host with a shadow root, and an element inside that root. */
function nested(): { host: HTMLElement; inner: HTMLElement } {
  const host = document.createElement('div');
  const inner = document.createElement('span');
  host.attachShadow({ mode: 'open' }).append(inner);
  document.body.append(host);
  return { host, inner };
}

describe('memoryOf', () => {
  it("finds the memory kept by a root around the node, through shadow roots, and the page's elsewhere", () => {
    const { host, inner } = nested();
    expect(memoryOf(inner)).toBe(pageMemory);
    const mine = new LocalMemory();
    keepMemory(host, mine);
    expect(memoryOf(inner)).toBe(mine);
    expect(memoryOf(document.body)).toBe(pageMemory);
    keepMemory(host, null);
    expect(memoryOf(inner)).toBe(pageMemory);
  });

  it("keeps two roots' sets apart, and out of the page's history", () => {
    const one = nested();
    const two = nested();
    keepMemory(one.host, new LocalMemory());
    keepMemory(two.host, new LocalMemory());
    new RememberedSet('cards', one.inner).set('x', true);
    expect(new RememberedSet('cards', one.inner).has('x')).toBe(true);
    expect(new RememberedSet('cards', two.inner).has('x')).toBe(false);
    expect(history.state).toBeNull();
  });
});
