// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { withDefaults } from '../core/strings.js';
import { defineElement } from '../core/define.js';
import { CaeMarkdown } from './cae-markdown.js';

defineElement('cae-markdown', CaeMarkdown);

describe('withDefaults', () => {
  it('keeps a default for a word not given', () => {
    expect(withDefaults({ a: 'A', b: 'B' }, { b: 'b', a: undefined })).toEqual({ a: 'A', b: 'b' });
    expect(withDefaults({ a: 'A' }, null)).toEqual({ a: 'A' });
  });
});

describe('cae-markdown', () => {
  it('renders the body, its split-off head apart, and the source on demand in the given words', async () => {
    const el = document.createElement('cae-markdown');
    el.text = 'HEAD line\n\n**bold**';
    el.split = (t) => ({ head: t.split('\n')[0] ?? '', body: t.split('\n').slice(2).join('\n') });
    el.strings = { showSource: 'Source' };
    document.body.append(el);
    await el.updateComplete;
    const root = el.shadowRoot!;
    expect(root.querySelector('.md-tele')?.textContent).toBe('HEAD line');
    expect(root.querySelector('.md-doc b')?.textContent).toBe('bold');
    const toggle = root.querySelector<HTMLButtonElement>('[part=toggle]')!;
    expect(toggle.textContent?.trim()).toBe('Source');
    toggle.click();
    await el.updateComplete;
    expect(root.querySelector('pre.df-text')?.textContent).toBe(el.text);
    expect(toggle.textContent?.trim()).toBe('Show rendered');
    el.remove();
  });
});
