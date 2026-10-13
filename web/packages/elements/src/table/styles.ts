// The look of `<cae-data-table>`. A row is a grid of the columns' tracks
// (`--cae-data-table-columns`, set from the columns' widths), so every row
// lines up with the header without a table layout pass.
import { css } from 'lit';

export const dataTableStyles = css`
  :host { display: block; }
  table { display: block; width: 100%; border-collapse: collapse; overflow-x: auto; }
  caption { display: block; text-align: start; }
  thead, tbody { display: block; }
  tr { display: grid; grid-template-columns: var(--cae-data-table-columns); column-gap: var(--cae-data-table-gap, 12px);
    align-items: center; padding: var(--cae-data-table-row-padding, 6px 12px); }
  th, td { display: block; min-width: 0; padding: 0; text-align: start; font-weight: inherit; }
  [data-align='end'] { text-align: end; font-variant-numeric: tabular-nums; }
  thead tr { color: var(--text-muted); font-size: var(--font-size-sm); border-bottom: 1px solid var(--line); }
  tbody tr { border-bottom: 1px solid var(--line); }
  tbody tr[data-key] { cursor: pointer; }
  table.passive tbody tr[data-key] { cursor: default; }
  tbody tr[data-key]:hover { background: var(--raise); }
  tbody tr[data-key]:focus-visible { outline-offset: -2px; }
  tbody tr[aria-current='true'] { background: var(--accent-bg); }
  tbody tr[data-tone='running'] { background: var(--status-running-bg); }
  tbody tr[data-tone='failed'] { background: color-mix(in srgb, var(--status-failed) 6%, transparent); box-shadow: inset 3px 0 0 var(--status-failed); }
  tr.spacer { display: block; padding: 0; border: 0; }
  tr.empty { display: block; border: 0; padding: 0; }
  tr.empty td { color: var(--text-muted); padding: 8px; }
  .sort { display: inline-flex; align-items: center; gap: 4px; padding: 0; border: 0; background: none; color: inherit; font: inherit; cursor: pointer; }
  .sort:hover { color: var(--text); }
  .arrow { font-size: 0.85em; }
`;
