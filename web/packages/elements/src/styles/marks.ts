// A status mark: a small square or round shape in a state's look (`data-tone` for
// its colour, `data-shape` for its shape), sized by `--m`. In a `.big` group a
// failed mark carries ✕, and a badge (`data-n`) is written in the mark.
import { css } from 'lit';

export const markStyles = css`
  .mark { width: var(--m); height: var(--m); padding: 0; margin: 0; border: 0; border-radius: 50%; background: var(--tone, var(--status-done)); opacity: 0.9;
    cursor: pointer; position: relative; transition: opacity 0.2s, transform 0.15s, background 0.3s; }
  .mark:not([data-tone]) { --tone: initial; }
  .mark[data-tone='muted'] { opacity: 0.55; }
  .mark[data-tone='running'] { opacity: 1; animation: breathe 1.4s ease-in-out infinite; }
  .mark[data-shape='ring'] { background: transparent; box-shadow: inset 0 0 0 1.5px var(--tone, var(--line2)); }
  .mark[data-shape='hatched'] { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, color-mix(in srgb, var(--tone) 55%, transparent) 2px 3px);
    box-shadow: inset 0 0 0 1.5px var(--tone); opacity: 1; }
  .mark[data-shape='square'] { border-radius: 2px; opacity: 1; }
  .big .mark[data-tone='failed']::after { content: '✕'; position: absolute; inset: 0; display: grid; place-items: center; color: var(--bg);
    font-size: calc(var(--m) - 3px); line-height: 1; font-weight: 700; }
  /* A badge (a count): in the mark; a small mark has a hole instead. */
  .mark[data-n]::after { content: ''; position: absolute; inset: 32%; border-radius: 50%; background: var(--card); }
  .big .mark[data-n]::after { content: attr(data-n); inset: 0; display: grid; place-items: center; border-radius: 0; background: none;
    font: 700 max(7px, calc(var(--m) - 4px)) / 1 var(--sans); color: var(--bg); letter-spacing: -0.5px; }
  .big .mark:is(:not([data-tone]), [data-tone='attention'], [data-tone='muted'])[data-n]::after { color: var(--text); }
  .mark:hover, .mark:focus-visible { transform: scale(1.4); outline: var(--focus-width) solid var(--text); outline-offset: 1px; z-index: 2; }
  .mark.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; z-index: 2; }
  @media (prefers-reduced-motion: reduce) {
    .mark { transition: none; }
    .mark[data-tone='running'] { animation: none; background: linear-gradient(90deg, var(--status-running) 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px var(--status-running); }
  }
`;
