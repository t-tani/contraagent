import type { ContractSpec } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { checkRowsFromContract, rootOf, rowOf, typeOk } from './check-rows.js';

const spec = (content: unknown, extra: Partial<ContractSpec> = {}): ContractSpec =>
  ({
    path: 'out/x.json',
    schema_name: 'Out',
    fields: [
      { name: 'title', type: 'string', required: true },
      { name: 'tags', type: 'list[str]', required: false },
    ],
    file: { exists: content !== undefined, content: content ?? null },
    ...extra,
  }) as ContractSpec;

describe('typeOk', () => {
  it.each([
    ['string', 'a', true],
    ['string', 1, false],
    ['integer', 2, true],
    ['integer', 2.5, false],
    ['number', 2.5, true],
    ['boolean', false, true],
    ['list[str]', ['a'], true],
    ['array', {}, false],
    ['object', {}, true],
    ['object', [], false],
    ['object', null, false],
    ['datetime', 'x', true],
  ])('%s against %j is %s', (t, v, ok) => {
    expect(typeOk(t, v)).toBe(ok);
  });
});

describe('checkRowsFromContract', () => {
  it('judges each field against the file, and names the fields the schema does not', () => {
    const rows = checkRowsFromContract(spec({ title: 3, extra: true }));
    expect(rows?.map((r) => [r.name, r.verdict, r.verdictLabel, r.hasValue])).toEqual([
      ['title', 'fail', 'wrong type', true],
      ['tags', 'none', 'absent (optional)', false],
      ['extra', 'warn', 'extra field', true],
    ]);
    expect(rows?.[0]).toMatchObject({ expected: 'string', optional: false, value: 3, tip: 'Expected string' });
    expect(rows?.[2]).toMatchObject({ extra: true, expected: 'not in the schema' });
  });

  it('marks a missing required field failed, and a present one passed', () => {
    expect(checkRowsFromContract(spec({ tags: [] }))?.map((r) => [r.name, r.verdict, r.verdictLabel])).toEqual([
      ['title', 'fail', 'missing'],
      ['tags', 'pass', 'passed'],
    ]);
  });

  it('lists the fields with no verdict when there is no file, or the file is not an object', () => {
    for (const s of [spec(undefined), spec([1, 2])]) {
      expect(checkRowsFromContract(s)?.map((r) => [r.name, r.verdict, r.verdictLabel, r.hasValue])).toEqual([
        ['title', 'none', '', false],
        ['tags', 'none', '', false],
      ]);
    }
  });

  it('is null for a text result', () => {
    expect(checkRowsFromContract(spec('hi', { schema_name: 'text', fields: [] }))).toBeNull();
    expect(checkRowsFromContract(spec('hi', { schema_name: 'RootModel[str]', fields: [] }))).toBeNull();
  });
});

describe('rowOf', () => {
  it('names the model of one line of a rows schema, and nothing for another schema', () => {
    expect(rowOf('Rows[Finding]')).toBe('Finding');
    expect(rowOf('Finding')).toBeNull();
    expect(rootOf('Rows[Finding]')).toBeNull();
  });
});
