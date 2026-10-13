// What the pipeline graph says about a node: its tasks done, the others by state.
import { describe, expect, it } from 'vitest';
import type { NodeCounts } from '../graph/types.js';
import { countOf, doneOf, exceptions, notDone, stateCounts, stateWord, where } from './words.js';

const counts = (c: Partial<NodeCounts>): NodeCounts => ({ total: 0, done: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, ...c });

describe('pipeline graph words', () => {
  it('counts the tasks done (done after retrying included), and skipped ones apart', () => {
    const c = counts({ total: 6, done: 4, skipped: 1, failed: 1 });
    expect(doneOf(c)).toBe('4 of 6 tasks done');
    expect(stateCounts(c, false)).toBe('4 done | 1 failed | 1 skipped');
  });

  it('names a node’s exceptions, most severe first, with its flow calls that stopped with an error', () => {
    const c = counts({ total: 9, done: 1, failed: 2, blocked: 1, running: 1, pending: 3, skipped: 1 });
    expect(exceptions({ counts: c, errors: 2 }, true)).toEqual([
      ['err', '2 failed'],
      ['err', '2 flow calls stopped with an error'],
      ['warn', '1 not started'],
      ['live', '1 running'],
      ['mut', '3 waiting'],
      ['mut', '1 skipped'],
    ]);
    expect(exceptions({ counts: counts({ total: 1, done: 1 }), errors: 1 }, true)).toEqual([['err', '1 flow call stopped with an error']]);
    expect(exceptions({ counts: counts({ total: 1, done: 1 }), errors: 0 }, true)).toEqual([]);
    expect(notDone(c, true)).toEqual(['2 failed', '1 not started', '1 running', '3 waiting', '1 skipped']);
  });

  it('says a pending task waits while the run runs, and did not run once it is over', () => {
    expect(stateWord('pending', true)).toBe('waiting');
    expect(stateWord('pending', false)).toBe('not run');
    expect(countOf('pending', 2, true)).toBe('2 waiting');
    expect(countOf('pending', 2, false)).toBe('2 not run');
    expect(stateWord('blocked', false)).toBe('not started');
    expect(exceptions({ counts: counts({ total: 2, pending: 2 }), errors: 0 }, false)).toEqual([['mut', '2 not run']]);
  });

  it('names a loop by its file and line', () => {
    expect(where(130, 'src/flows/flow.py')).toBe('flow.py:130');
    expect(where(130)).toBe('line 130');
  });
});
