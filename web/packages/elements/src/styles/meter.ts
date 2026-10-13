// A duration bar under a time (the task table and History).
import { css } from 'lit';

/** A duration: it measures, it does not judge (red only for a failed attempt). */
export const meterStyles = css`
  .jdur { position: relative; display: block; height: 6px; border-radius: 3px; background: var(--track); overflow: hidden; margin-top: 2px; }
  .jdur i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--meter); }
  .jdur i.bad { background: var(--status-failed); }
`;
