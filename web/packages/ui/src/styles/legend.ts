// A legend: a swatch and a word per entry (the graph, the timeline, the token bars).
import { css } from 'lit';

export const legendStyles = css`
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--text-muted); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
`;
