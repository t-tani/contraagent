// Labelled facts in a row that wraps (the run's process, a task's definition).
import { css } from 'lit';

export const factStyles = css`
  .drv-facts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: var(--font-size-md); }
  .drv-facts i { font-style: normal; color: var(--text-muted); margin-right: 5px; font-size: var(--font-size-sm); }
`;
