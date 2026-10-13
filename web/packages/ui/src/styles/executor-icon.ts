// What ran a task, as a small icon before its name: an agent task or a Python task.
import { css } from 'lit';

/** Who ran it (identity, a small cue): `.k-ic` for a Python task, `.k-ic.llm` for an agent task. */
export const executorIconStyles = css`
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: var(--font-size-sm); background: var(--raise); color: var(--text-muted); flex: none; }
  .k-ic.llm { background: var(--agent-bg); color: var(--agent); }
`;
