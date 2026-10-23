// @vitest-environment happy-dom
import { render } from 'lit';
import { describe, expect, it } from 'vitest';
import { wholePercents, shareBar, sharePercent, type SharePart } from './share-bar.js';

const parts = (...values: number[]): SharePart[] => values.map((value, i) => ({ id: `p${i}`, label: `part ${i}`, value, color: `var(--series-${i + 1})`, text: `${value}` }));

function draw(p: readonly SharePart[], labelAt?: number): HTMLElement {
  const host = document.createElement('div');
  render(shareBar(p, { label: 'Share', labelAt }), host);
  return host;
}

describe('wholePercents', () => {
  it('sums to exactly 100, the largest remainders rounding up', () => {
    for (const values of [[1, 1, 1], [2, 1], [0.3, 0.3, 0.4], [999, 1], [5, 3, 2, 1, 1, 1]]) {
      expect(wholePercents(values).reduce((a, v) => a + v, 0)).toBe(100);
    }
    expect(wholePercents([1, 1, 1])).toEqual([34, 33, 33]);
  });

  it('is all 0 when nothing was used', () => {
    expect(wholePercents([0, 0])).toEqual([0, 0]);
  });

  it('says <1% for a part above 0 that rounds to 0', () => {
    const [big, small] = wholePercents([999, 1]);
    expect(sharePercent(small!, 1)).toBe('<1%');
    expect(sharePercent(big!, 999)).toBe('100%');
  });
});

describe('shareBar', () => {
  it('leaves the names under the bar out when asked', () => {
    const host = document.createElement('div');
    render(shareBar(parts(3, 1), { names: false }), host);
    expect(host.querySelectorAll('.share-seg')).toHaveLength(2);
    expect(host.querySelector('.share-names')).toBeNull();
  });

  it('draws a segment per part above 0, as wide as its share, in the order given', () => {
    const host = draw(parts(3, 0, 1));
    const segs = [...host.querySelectorAll<HTMLElement>('.share-seg')];
    expect(segs.map((s) => s.dataset['id'])).toEqual(['p0', 'p2']);
    expect(segs.map((s) => s.style.flexGrow)).toEqual(['0.75', '0.25']);
    expect(segs[0]!.style.background).toContain('--series-1');
  });

  it('names each segment for a screen reader and in its tooltip', () => {
    const host = draw(parts(3, 1));
    const seg = host.querySelector<HTMLElement>('.share-seg')!;
    expect(seg.getAttribute('aria-label')).toBe('part 0 | 75% | 3');
    expect(seg.querySelector('.share-tip')!.textContent).toBe('part 0 | 75% | 3');
    expect(host.querySelector('.share-bar')!.getAttribute('aria-label')).toBe('Share');
  });

  it('names a part under the bar only when it is wide enough', () => {
    const host = draw(parts(9, 1), 0.15);
    const names = [...host.querySelectorAll('.share-names span')].map((s) => s.textContent.trim());
    expect(names).toEqual(['part 0 90%', '']);
  });
});
