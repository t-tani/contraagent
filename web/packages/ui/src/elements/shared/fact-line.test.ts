// @vitest-environment happy-dom
import { render } from 'lit';
import { describe, expect, it } from 'vitest';
import { factLine } from './fact-line.js';

describe('factLine', () => {
  it('renders one .f span per fact, separated by " | "', () => {
    const host = document.createElement('div');
    render(factLine(['6 tasks', '6 attempts', 'a | b']), host);
    expect([...host.querySelectorAll('.f')].map((e) => e.textContent)).toEqual(['6 tasks', '6 attempts', 'a | b']);
    expect(host.textContent).toBe('6 tasks | 6 attempts | a | b');
  });

  it('renders nothing for no facts', () => {
    const host = document.createElement('div');
    render(factLine([]), host);
    expect(host.querySelectorAll('.f')).toHaveLength(0);
    expect(host.textContent).toBe('');
  });
});
