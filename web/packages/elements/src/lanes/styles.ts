// The look of `<cae-lanes>`: a label column, then a track per lane with its
// bars; a bar's look is its colour (`--bar`) and its pattern (`data-pattern`),
// the same on the bar and on its swatch in the legend.
import { css } from 'lit';

export const lanesStyles = css`
  :host { display: block; container-type: inline-size; --label: var(--cae-lanes-label-width, 112px); }
  /* narrow (the host is a container): a narrower label column, and the axis' first, middle and last times only */
  @container (max-width: 760px) { .lanes { --label: var(--cae-lanes-label-width, 78px); } }
  @container (max-width: 480px) { .axis span:nth-child(even) { display: none; } }
  .lanes { position: relative; }
  .axis { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; color: var(--text-muted); margin: 0 0 6px calc(var(--label) + 8px); }
  .lane { display: grid; grid-template-columns: var(--label) minmax(0, 1fr); gap: 8px; align-items: center; min-height: 24px; padding: 4px 0; }
  .name { font-size: 11.5px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .track { position: relative; height: calc(var(--rows, 1) * 14px + 2px); border-radius: 4px;
    background: repeating-linear-gradient(90deg, color-mix(in srgb, var(--text) 5%, transparent) 0 1px, transparent 1px 10%); }
  .bar { position: absolute; top: calc(var(--row, 0) * 14px + 2px); height: 12px; border-radius: 4px; min-width: 3px; cursor: default;
    transform-origin: left center; transition: width 1s linear; }
  .anim .bar:not(.running) { animation: growx 0.6s var(--ease) both; }
  :is(.bar, .legend i)[data-pattern] { background: var(--bar); }
  :is(.bar, .legend i)[data-pattern='hatched'] { background: repeating-linear-gradient(135deg, var(--bar) 0 3px, color-mix(in srgb, var(--bar) 55%, var(--bg)) 3px 5px); }
  :is(.bar, .legend i)[data-pattern='outline'] { background: none; box-shadow: inset 0 0 0 1.5px var(--bar); }
  :is(.bar, .legend i)[data-pattern='striped'] { background: repeating-linear-gradient(45deg, var(--bar) 0 6px, color-mix(in srgb, var(--bar) 60%, var(--bg)) 6px 12px);
    background-size: 17px 17px; }
  .bar[data-pattern='striped'] { animation: stripes 0.8s linear infinite; box-shadow: 0 0 12px color-mix(in srgb, var(--bar) 45%, transparent); }
  .bar:hover { filter: brightness(1.2); }
  .now { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--status-running); border-radius: 2px; box-shadow: 0 0 10px var(--status-running); }
  .legend { margin-top: 10px; }
  .legend + .legend { margin-top: 4px; }
`;
