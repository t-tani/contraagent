// Chips: a row of chips (stages: done, current, to come), a task's name, a tag, a key.
import { css } from 'lit';

export const chipStyles = css`
  .tag { font-size: var(--font-size-xs); padding: 0 7px; border-radius: var(--radius-pill); border: 1px solid var(--line2); color: var(--text-muted); white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { font-size: var(--font-size-sm); padding: 1px 8px; border-radius: var(--radius-pill); border: 1px solid var(--line); color: var(--text-muted); white-space: nowrap; }
  .chip[data-tone='done'] { color: var(--text-2); }
  .chip[data-tone='done'] > [aria-hidden] { color: var(--tone); font-weight: 700; }
  .chip[data-tone='running'] { background: var(--tone); color: var(--bg); border-color: var(--tone); font-weight: 600; animation: ping 1.6s var(--ease) infinite; }
  .chip.todo { opacity: 0.65; }
  .taskchip { display: inline-block; font: inherit; font-family: var(--mono); font-size: var(--font-size-sm); line-height: 1.5; padding: 0 8px;
    border-radius: var(--radius-pill); border: 1px solid var(--line); background: var(--raise); color: var(--text-2); white-space: nowrap; }
  button.taskchip { cursor: pointer; }
  button.taskchip:hover { border-color: var(--accent); color: var(--text); }
  .kbd { font-family: var(--mono); font-size: var(--font-size-xs); border: 1px solid var(--line2); border-bottom-width: 2px;
    border-radius: var(--radius-sm); padding: 0 4px; color: var(--text-muted); }
`;
