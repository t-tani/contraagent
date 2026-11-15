// @vitest-environment happy-dom
// The settings behind one button of the header: the theme, the language and the keys.
import { describe, expect, it } from 'vitest';
import './ca-settings.js';
import type { CaSettings } from './ca-settings.js';

const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim();

async function settings(props: Partial<CaSettings> = {}): Promise<CaSettings> {
  const el: CaSettings = document.createElement('ca-settings');
  Object.assign(el, props);
  document.body.append(el);
  await el.updateComplete;
  return el;
}

describe('ca-settings', () => {
  it('names its button, and lists every theme as a radio with the choice checked', async () => {
    const el = await settings({ theme: 'nord', system: 'contraagent-light' });
    const root = el.shadowRoot!;
    expect(root.querySelector('.trig')!.getAttribute('aria-label')).toBe('Settings');
    const items = [...root.querySelectorAll<HTMLElement>('.item')];
    expect(items.map((i) => i.dataset['theme'])).toEqual(['system', 'contraagent-dark', 'contraagent-light', 'github-dark', 'github-light', 'one-dark', 'nord', 'high-contrast']);
    expect(items.every((i) => i.getAttribute('role') === 'radio')).toBe(true);
    expect(items.filter((i) => i.getAttribute('aria-checked') === 'true').map((i) => i.dataset['theme'])).toEqual(['nord']);
    // `system` says which theme it shows now; one tab stop, on the chosen theme.
    expect(text(items[0])).toBe('System contraagent Light');
    expect(items.filter((i) => i.tabIndex === 0).map((i) => i.dataset['theme'])).toEqual(['nord']);
    el.remove();
  });

  it('sends the theme chosen, and stays open for the next choice', async () => {
    const el = await settings();
    const sent: string[] = [];
    el.addEventListener('ca-choose-theme', (e) => sent.push(e.detail.theme));
    el.shadowRoot!.querySelector<HTMLElement>('.item[data-theme="one-dark"]')!.click();
    await el.updateComplete;
    expect(sent).toEqual(['one-dark']);
    expect(el.shadowRoot!.querySelector('.item[aria-checked="true"]')!.getAttribute('data-theme')).toBe('one-dark');
    el.remove();
  });

  it('offers the languages when there are two or more, and sends the one chosen', async () => {
    const one = await settings({ locales: [{ value: 'en', label: 'English' }], locale: 'en' });
    expect(one.shadowRoot!.querySelector('cae-segmented')).toBeNull();
    one.remove();
    const el = await settings({ locales: [{ value: 'en', label: 'English' }, { value: 'ja', label: '日本語' }], locale: 'en' });
    const sent: string[] = [];
    el.addEventListener('ca-choose-locale', (e) => sent.push(e.detail.locale));
    const langs = el.shadowRoot!.querySelector('cae-segmented')!;
    await langs.updateComplete;
    langs.shadowRoot!.querySelector<HTMLElement>('button[lang="ja"]')!.click();
    expect(sent).toEqual(['ja']);
    el.remove();
  });

  it('lists the keys that work, and none when there are none', async () => {
    const el = await settings({ keys: [{ keys: ['1', '7'], does: 'Tabs' }, { keys: ['r'], does: 'Runs' }] });
    const list = el.shadowRoot!.querySelector('.keys')!;
    expect([...list.querySelectorAll('dt')].map(text)).toEqual(['1–7', 'r']);
    expect([...list.querySelectorAll('dd')].map(text)).toEqual(['Tabs', 'Runs']);
    el.remove();
    const none = await settings();
    expect(none.shadowRoot!.querySelector('.keys')).toBeNull();
    none.remove();
  });
});
