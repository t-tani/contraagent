import { describe, expect, it } from 'vitest';
import { parentLayer, resolveLayer, splitLayer } from './layer.js';
import { AT, F, LOOP, RUN, ft, planOf, reviewRun } from './plans.fixture.js';

describe('layer segments', () => {
  it('splits off the loop box entered at the end', () => {
    expect(splitLayer([RUN, LOOP, 'loop:7'])).toEqual({ path: [RUN, LOOP], loop: 'loop:7' });
    expect(splitLayer([RUN])).toEqual({ path: [RUN], loop: null });
  });

  it('goes up one level, to the layer the graph opens on at most', () => {
    expect(parentLayer([RUN, LOOP, 'loop:7'], [RUN])).toEqual([RUN, LOOP]);
    expect(parentLayer([RUN, LOOP], [RUN])).toEqual([]);
    expect(parentLayer([RUN], [RUN])).toBeNull();
  });
});

describe('resolveLayer', () => {
  const plan = reviewRun({ a: 1, b: 2 });
  it('keeps a layer the plan has, with its loop box', () => {
    expect(resolveLayer(plan, [RUN, LOOP])).toEqual([RUN, LOOP]);
    expect(resolveLayer(plan, [RUN, LOOP, `loop:${AT}`])).toEqual([RUN, LOOP, `loop:${AT}`]);
  });
  it("finds a function named by its qualified name, or by its name, when the plan reaches it by one flow path", () => {
    expect(resolveLayer(plan, [LOOP])).toEqual([RUN, LOOP]);
    expect(resolveLayer(plan, ['review_loop'])).toEqual([RUN, LOOP]);
    expect(resolveLayer(plan, ['review_loop', `loop:${AT}`])).toEqual([RUN, LOOP, `loop:${AT}`]);
  });
  it('names nothing for a layer the plan does not have', () => {
    expect(resolveLayer(plan, ['flows.gone'])).toBeNull();
    expect(resolveLayer(plan, [RUN, LOOP, 'loop:99'])).toBeNull();
    // A function the plan reaches by two flow paths names no one layer.
    const SUB = 'flows.sub';
    const two = planOf([ft('x-u', 'u', 'x', 'done', [F(RUN), F(SUB)]), ft('y-u', 'u', 'y', 'done', [F(RUN), F(LOOP), F(SUB)])]);
    expect(resolveLayer(two, [SUB])).toBeNull();
    expect(resolveLayer(two, [RUN, LOOP, SUB])).toEqual([RUN, LOOP, SUB]);
  });
});
