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
  :host { display: block; max-width: 100%; }
  table { width: auto; max-width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 11.5px; color: var(--text-muted);
    font-weight: 600; padding: 4px 20px 4px 0; border-bottom: 1px solid var(--line); }
  td { padding: 5px 20px 5px 0; border: 0; border-bottom: 1px solid var(--line); vertical-align: baseline; font-size: 12.5px; }
  th:last-child, td:last-child { padding-right: 0; }
  td.value { overflow-wrap: anywhere; }
  tbody tr:last-child td { border-bottom: 0; }
  td:first-child { white-space: nowrap; font-weight: 600; }
  td:last-child { white-space: nowrap; }
  i { font-style: normal; color: var(--text-muted); font-size: 11px; margin-left: 4px; }
  .js { color: var(--code-string); }
  .jn { color: var(--code-number); }
`;
