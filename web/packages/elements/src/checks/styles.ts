// The look of `<cae-check-table>`, and of a verdict (`verdict()`) wherever a
// host shows one.
import { css } from 'lit';

/** A verdict: ✓ and its word quiet, ✕ and its word in the failed tone, a warning in the attention tone. */
export const verdictStyles = css`
  .verdict { font-size: 12px; }
  .verdict[data-verdict='pass'] { color: var(--text-2); }
  .verdict[data-verdict='pass'] > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .verdict[data-verdict='fail'] { color: var(--status-failed); font-weight: 600; }
  .verdict[data-verdict='warn'] { color: var(--status-attention); }
  .verdict[data-verdict='none'] { color: var(--text-muted); }
`;

/** Sized to its content, so a verdict sits next to the value it judges; a long value wraps. */
export const checkTableStyles = css`
  :host { display: block; max-width: 100%; container-type: inline-size; }
  table { width: auto; max-width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 11.5px; color: var(--text-muted);
    font-weight: 600; padding: 4px 20px 4px 0; border-bottom: 1px solid var(--line); }
  td { padding: 5px 20px 5px 0; border: 0; border-bottom: 1px solid var(--line); vertical-align: baseline; font-size: 12.5px; }
  th:last-child, td:last-child { padding-right: 0; }
  td.value { overflow-wrap: anywhere; }
  tbody tr:last-child td { border-bottom: 0; }
  /* a name stays on one line while the table has the room, and breaks where it must */
  td:first-child { font-weight: 600; overflow-wrap: anywhere; }
  td:last-child { white-space: nowrap; }
  i { font-style: normal; color: var(--text-muted); font-size: 11px; margin-left: 4px; }
  /* a phone: one field a block, its name and verdict on the first line, what is expected and the value under them */
  @container (max-width: 440px) {
    table, tbody { display: block; }
    thead { display: none; }
    tbody tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: 12px; row-gap: 2px; padding: 6px 0; border-bottom: 1px solid var(--line); }
    tbody tr:last-child { border-bottom: 0; }
    td { padding: 0; border: 0; }
    td:nth-child(1) { grid-area: 1 / 1; }
    td:nth-child(2), td:nth-child(3) { grid-column: 1 / -1; }
    td:nth-child(4) { grid-area: 1 / 2; }
  }
  .js { color: var(--code-string); }
  .jn { color: var(--code-number); }
`;
