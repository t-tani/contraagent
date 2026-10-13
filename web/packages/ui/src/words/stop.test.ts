import { describe, expect, it } from 'vitest';
import { stopLabel } from './stop.js';

describe('stopLabel', () => {
  it('names stops in words, and an unknown one as unknown with its value', () => {
    expect([stopLabel('completed'), stopLabel('invalid_input'), stopLabel('invalid_output'), stopLabel('custom_stop'), stopLabel('')]).toEqual([
      'done',
      'not started (input missing or failed checks)',
      'failed checks',
      'unknown (custom_stop)',
      '—',
    ]);
    expect(stopLabel('invalid_input', 'invalid input: /r/out/a.json: required input is missing')).toBe('not started (input missing)');
    expect(stopLabel('invalid_input', 'invalid input: /r/out/a.json: field x: wrong type')).toBe('not started (input failed checks)');
  });
});
