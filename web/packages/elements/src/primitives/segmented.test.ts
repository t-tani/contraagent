// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeSegmented } from './segmented.js';

defineElement('cae-segmented', CaeSegmented);

async function mount(value = 'b'): Promise<{ el: CaeSegmented; radios: () => HTMLButtonElement[]; changes: string[] }> {
  const el = document.createElement('cae-segmented');
  el.label = 'Pick';
  el.options = [
    { value: 'a', label: 'A' },
    { value: 'b', label: 'B' },
    { value: 'c', label: 'C', lang: 'ja' },
  ];
  el.value = value;
  const changes: string[] = [];
  el.addEventListener('cae-change', (e) => changes.push(e.detail.value));
  document.body.append(el);
  await el.updateComplete;
  const radios = () => [...el.shadowRoot!.querySelectorAll<HTMLButtonElement>('[role=radio]')];
  return { el, radios, changes };
}

const key = (target: HTMLElement, k: string) => target.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, composed: true }));

describe('cae-segmented', () => {
  it('is a radio group with one tab stop, on the chosen option', async () => {
    const { el, radios } = await mount();
    expect(el.shadowRoot!.querySelector('[role=radiogroup]')?.getAttribute('aria-label')).toBe('Pick');
    expect(radios().map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    expect(radios().map((r) => r.tabIndex)).toEqual([-1, 0, -1]);
    expect(radios()[1]!.getAttribute('part')).toBe('option option-selected');
    expect(radios()[2]!.lang).toBe('ja');
    el.remove();
  });

  it('chooses with a click and sends cae-change once', async () => {
    const { el, radios, changes } = await mount();
    radios()[0]!.click();
    radios()[0]!.click();
    await el.updateComplete;
    expect(changes).toEqual(['a']);
    expect(el.value).toBe('a');
    expect(radios()[0]!.getAttribute('aria-checked')).toBe('true');
    el.remove();
  });

  it('chooses with the arrow keys (wrapping), Home and End', async () => {
    const { el, radios, changes } = await mount();
    key(radios()[1]!, 'ArrowRight');
    await el.updateComplete;
    key(radios()[2]!, 'ArrowRight');
    await el.updateComplete;
    key(radios()[0]!, 'ArrowLeft');
    await el.updateComplete;
    key(radios()[2]!, 'Home');
    await el.updateComplete;
    key(radios()[0]!, 'End');
    await el.updateComplete;
    expect(changes).toEqual(['c', 'a', 'c', 'a', 'c']);
    expect(radios().map((r) => r.tabIndex)).toEqual([-1, -1, 0]);
    el.remove();
  });
});
