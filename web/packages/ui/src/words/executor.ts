// What ran a task, as a small icon before its name: ✦ an agent task, ⚙ a Python task.
import { icon } from '@contraagent/elements/primitives';
import { css, type TemplateResult } from 'lit';

/** The glyph of who runs a task. */
export const executorGlyph = (python: boolean): string => (python ? '⚙' : '✦');

/**
 * Who ran a task, as an icon (`.k-ic`, `.k-ic.llm` for an agent task, unless `cls`
 * names other classes). With a label, the label is its tooltip and what a screen
 * reader reads; without one, it is hidden from screen readers.
 */
export function executorIcon(python: boolean, label?: string | null, cls?: string): TemplateResult {
  return icon(executorGlyph(python), label, { cls: cls ?? `k-ic ${python ? '' : 'llm'}` });
}

/** Who ran it (identity, a small cue): `.k-ic` for a Python task, `.k-ic.llm` for an agent task. */
export const executorIconStyles = css`
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: var(--font-size-sm); background: var(--raise); color: var(--text-muted); flex: none; }
  .k-ic.llm { background: var(--agent-bg); color: var(--agent); }
`;
