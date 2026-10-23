// What `<cae-stat-tiles>` shows: a tile per figure.
import type { Tone } from '../core/tone.js';
import type { Fact } from '../primitives/fact-line.js';

/** A figure as a tile: its name, its value and the lines under it. */
export interface StatTile {
  /** Unique among the tiles: `data-id` on the tile, and the `id` of `cae-action`. */
  id: string;
  label: string;
  /** A number counts up to a new value, and the tile bumps when it changes; a text is shown as it is. */
  value: number | string;
  /** The status the figure is in: its value, the mark before its label and an edge take the tone. None (or `neutral`) for a plain figure. */
  tone?: Tone;
  /** The tile's tooltip. */
  tip?: string;
  /** The lines under the value, each a row of facts (`factLine`); an empty line keeps its place. */
  sub?: readonly (readonly (string | Fact)[])[];
  /** Makes the whole tile a link named `label`: a click sends `cae-action` with the tile's id and this id. */
  action?: { id: string; label: string };
}
