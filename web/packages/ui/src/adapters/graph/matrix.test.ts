import { describe, expect, it } from 'vitest';
import { passMatrix, sortRows } from './matrix.js';
import { AT, LOOP, RUN, SCAN, nestedLoops, reviewRun } from './plans.fixture.js';

describe('passMatrix', () => {
  it('unrolls a loop box into units by (node, pass), leaving out what no unit reached', () => {
    const plan = reviewRun({ a: 1, b: 3, c: 0, d: 2 }, { failed: 'd' });
    const m = passMatrix(plan, [RUN, LOOP], `loop:${AT}`);
    expect(m?.box.passes).toBe(2 + 1);
    // c never entered the loop: no row.
    expect(m?.rows.map((r) => [r.unit, r.passes, r.state])).toEqual([['a', 1, 'done'], ['b', 3, 'done'], ['d', 2, 'failed']]);
    expect(m?.columns.map((c) => `${c.node.label}${c.passes.join('.')}`)).toEqual(['fix1', 'score1', 'check1', 'fix2', 'score2', 'check2', 'fix3', 'score3', 'check3']);
    expect(m?.head.map((r) => r.map((h) => (h.type === 'pass' ? `P${h.pass}x${h.span}` : h.type === 'node' ? h.node.label : 'loop')))).toEqual([
      ['P1x3', 'P2x3', 'P3x3'],
      ['fix', 'score', 'check', 'fix', 'score', 'check', 'fix', 'score', 'check'],
    ]);
    expect(m?.rows[2]?.cells.map((c) => c?.key ?? null)).toEqual(['fix-d', 'score-d', 'check-d~2', 'fix-d~2', null, null, null, null, null]);
    expect(passMatrix(plan, [RUN, LOOP], 'loop:99')).toBeNull();
    // Sorted by passes (most first) or by status (most severe first); a tie keeps the order.
    expect(sortRows(m?.rows ?? [], 'passes').map((r) => r.unit)).toEqual(['b', 'd', 'a']);
    expect(sortRows(m?.rows ?? [], 'state').map((r) => r.unit)).toEqual(['d', 'a', 'b']);
  });

  it("unrolls nested loops: an inner loop's passes within each pass of the outer one", () => {
    const plan = nestedLoops();
    const outerBox = 'loop:30';
    const innerBox = 'loop:30.33';

    // The outer loop's passes: each outer pass a group of columns, the inner loop's passes nested in it.
    const o = passMatrix(plan, [RUN, SCAN], outerBox);
    expect(o?.columns.map((c) => `${c.node.label}${c.passes.join('.')}`)).toEqual(['propose1', 'verify1.1', 'refine1.1', 'verify1.2', 'propose2', 'verify2.1']);
    const label = (h: NonNullable<typeof o>['head'][number][number]) =>
      h.type === 'pass' ? `P${h.pass}x${h.span}` : h.type === 'loop' ? `loop x${h.span}` : `${h.node.label}/${h.rows}`;
    expect(o?.head.map((r) => r.map(label))).toEqual([
      ['P1x4', 'P2x2'],
      ['propose/3', 'loop x3', 'propose/3', 'loop x1'],
      ['P1x2', 'P2x1', 'P1x1'],
      ['verify/1', 'refine/1', 'verify/1', 'verify/1'],
    ]);
    expect(o?.rows.map((r) => [r.unit, r.passes, r.cells.map((c) => c?.key ?? null)])).toEqual([
      ['a', 2, ['propose-a', 'verify-a', 'refine-a', 'verify-a~2', 'propose-a~2', 'verify-a~3']],
      ['b', 1, ['propose-b', 'verify-b', null, null, null, null]],
    ]);
    // The inner loop's passes: counted within each pass of the outer loop.
    const i = passMatrix(plan, [RUN, SCAN], innerBox);
    expect(i?.columns.map((c) => `${c.node.label}${c.passes.join('.')}`)).toEqual(['verify1', 'refine1', 'verify2']);
    expect(i?.rows.map((r) => [r.unit, r.passes, r.cells.map((c) => c?.key ?? null)])).toEqual([
      ['a', 3, ['verify-a~3', 'refine-a', 'verify-a~2']],
      ['b', 1, ['verify-b', null, null]],
    ]);
    // a ran verify in inner pass 1 twice (outer passes 1 and 2): that column holds both.
    expect(i?.rows[0]?.cells[0]).toMatchObject({ count: 2, state: 'failed' });
  });
});
