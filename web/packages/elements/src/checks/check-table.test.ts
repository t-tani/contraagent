// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeCheckTable } from './check-table.js';
import type { CheckRow } from './types.js';

defineElement('cae-check-table', CaeCheckTable);

const ROWS: CheckRow[] = [
  { name: 'title', expected: 'string', hasValue: true, value: 'Hello', verdict: 'pass', verdictLabel: 'passed' },
  { name: 'count', expected: 'integer', hasValue: true, value: 'x', verdict: 'fail', verdictLabel: 'wrong type', tip: 'Expected integer' },
  { name: 'tags', expected: 'list[str]', optional: true, hasValue: true, value: ['a', 'b', 'c', 'd'], verdict: 'pass', verdictLabel: 'passed' },
  { name: 'note', expected: 'string', optional: true, hasValue: false, verdict: 'none', verdictLabel: 'absent' },
  { name: 'more', expected: 'not expected', extra: true, hasValue: true, value: { a: 1 }, verdict: 'warn', verdictLabel: 'extra' },
];

async function mount(props: Partial<CaeCheckTable> = {}) {
  const el = document.createElement('cae-check-table');
  Object.assign(el, { rows: ROWS, ...props });
  document.body.append(el);
  await el.updateComplete;
  return el;
}

const cells = (tr: Element) => [...tr.querySelectorAll('td')].map((td) => td.textContent?.replace(/\s+/g, ' ').trim());

describe('cae-check-table', () => {
  it('draws a row per name: what it must be, what it is, the verdict', async () => {
    const el = await mount();
    const rows = [...el.shadowRoot!.querySelectorAll('[part="row"]')];
    expect([...el.shadowRoot!.querySelectorAll('th')].map((th) => th.textContent)).toEqual(['Name', 'Expected', 'Value', 'Check']);
    expect(rows.map(cells)).toEqual([
      ['title', 'string', '"Hello"', '✓ passed'],
      ['count', 'integer', '"x"', '✕ wrong type'],
      ['tags', 'list[str] optional', '4 items "a", "b", "c", …', '✓ passed'],
      ['note', 'string optional', '—', 'absent'],
      ['more', 'not expected', 'object a', 'extra'],
    ]);
  });

  it('marks each verdict, with its tooltip; the mark is hidden from screen readers', async () => {
    const el = await mount();
    const v = [...el.shadowRoot!.querySelectorAll<HTMLElement>('[part="verdict"]')];
    expect(v.map((x) => x.dataset['verdict'])).toEqual(['pass', 'fail', 'pass', 'none', 'warn']);
    expect(v[1]!.title).toBe('Expected integer');
    expect(v[0]!.querySelector('[aria-hidden="true"]')?.textContent).toBe('✓');
  });

  it('without values, shows the names and what each must be', async () => {
    const el = await mount({ showValues: false, strings: { name: 'Field' } });
    expect([...el.shadowRoot!.querySelectorAll('th')].map((th) => th.textContent)).toEqual(['Field', 'Expected']);
    expect(cells(el.shadowRoot!.querySelector('[part="row"]')!)).toEqual(['title', 'string']);
  });
});
