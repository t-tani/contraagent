// @vitest-environment happy-dom
import { render } from 'lit';
import { describe, expect, it } from 'vitest';
import { icon } from './icon.js';
import { legend } from './legend.js';
import { markOf, pill, statusChip, statusWord } from './pill.js';

const draw = (t: unknown): HTMLElement => {
  const host = document.createElement('div');
  render(t, host);
  return host;
};

describe('pill', () => {
  it('sets data-tone, data-mark and part from its tone', () => {
    const el = draw(pill({ text: 'failed', tone: 'failed', title: 'timeout' })).querySelector('span')!;
    expect(el.className.trim()).toBe('pill');
    expect(el.dataset['tone']).toBe('failed');
    expect(el.dataset['mark']).toBe('failed');
    expect(el.getAttribute('part')).toBe('pill tone-failed');
    expect(el.title).toBe('timeout');
    expect(el.textContent).toBe('failed');
  });

  it('has no data-tone when neutral, and a mark only where asked', () => {
    const neutral = draw(pill({ text: 'x' })).querySelector('span')!;
    expect(neutral.hasAttribute('data-tone')).toBe(false);
    expect(neutral.hasAttribute('data-mark')).toBe(false);
    expect(neutral.getAttribute('part')).toBe('pill tone-neutral');
    expect(draw(pill({ text: 'x', tone: 'attention', mark: null })).querySelector('span')!.hasAttribute('data-mark')).toBe(false);
    expect(draw(pill({ text: 'x', tone: 'muted', mark: 'pending' })).querySelector('span')!.dataset['mark']).toBe('pending');
  });

  it('marks done, failed and attention by default', () => {
    expect(['done', 'failed', 'attention', 'running', 'muted', 'neutral'].map((t) => markOf(t as never))).toEqual(['done', 'failed', 'pending', null, null, null]);
  });

  it('draws a status word and a chip of a class of their own', () => {
    expect(draw(statusWord({ text: 'done', tone: 'done', cls: 'two' })).querySelector('span')!.className.trim()).toBe('jstop two');
    const chip = draw(statusChip('ct-chip', { text: 'passed', tone: 'done' })).querySelector('span')!;
    expect(chip.className.trim()).toBe('ct-chip');
    expect(chip.dataset['tone']).toBe('done');
  });
});

describe('legend and icon', () => {
  it('draws a list of entries, a swatch only where one is given', () => {
    const host = draw(legend([{ label: 'passed', tone: 'done', shape: 'round' }, { label: 'mine', swatch: 'red' }, { label: '3 more' }], { label: 'States' }));
    const list = host.querySelector('[role=list]')!;
    expect(list.getAttribute('aria-label')).toBe('States');
    expect(list.getAttribute('part')).toBe('legend');
    const items = [...list.querySelectorAll('[role=listitem]')];
    expect(items.map((i) => i.textContent)).toEqual(['passed', 'mine', '3 more']);
    expect(items[0]!.querySelector('i')!.dataset['tone']).toBe('done');
    expect(items[1]!.querySelector('i')!.getAttribute('style')).toContain('red');
    expect(items[2]!.querySelector('i')).toBeNull();
  });

  it('hides an icon without a label, and names one with a label', () => {
    expect(draw(icon('⚙')).querySelector('span')!.getAttribute('aria-hidden')).toBe('true');
    const named = draw(icon('⚙', 'Python task', { cls: 'k-ic' })).querySelector('span')!;
    expect(named.title).toBe('Python task');
    expect(named.className).toBe('k-ic');
    expect(named.querySelector('.sr')!.textContent).toBe('Python task');
  });
});
