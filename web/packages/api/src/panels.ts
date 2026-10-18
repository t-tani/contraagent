// Panel bodies: what a pipeline's own view returns (`monitor.Panel`). A typed body
// (tiles, a table, charts, code, a tree, blocks of them) is drawn with the monitor's elements;
// any other JSON object is shown as a JSON tree.
import type { components } from './schema.js';
import type { JsonObject, PanelInfo } from './types.js';

type S = components['schemas'];

export type TilesBody = S['TilesBody'];
export type PanelTile = S['PanelTile'];
export type TableBody = S['TableBody'];
export type TableColumn = S['TableColumn'];
export type ColumnsBody = S['ColumnsBody'];
export type LinesBody = S['LinesBody'];
export type HeatmapBody = S['HeatmapBody'];
export type HBarsBody = S['HBarsBody'];
export type HBar = S['HBar'];
export type StatusGridBody = S['StatusGridBody'];
export type GridCell = S['GridCell'];
export type NoteBody = S['NoteBody'];
export type CodeBody = S['CodeBody'];
export type TreeBody = S['TreeBody'];
export type EmbedBody = S['EmbedBody'];
export type TreeNode = S['TreeNode'];
export type TreeLink = S['TreeLink'];
export type BlocksBody = S['BlocksBody'];
export type ChartSeries = S['ChartSeries'];
/** How a number of a body is written: `pct` is a fraction (0.97 is 97%), `duration` seconds, `datetime` an ISO time. */
export type ValueFormat = NonNullable<TableColumn['format']>;

/** A body with a `type`: drawn with the monitor's own elements. */
export type TypedPanelBody =
  | TilesBody
  | TableBody
  | ColumnsBody
  | LinesBody
  | HeatmapBody
  | HBarsBody
  | StatusGridBody
  | NoteBody
  | CodeBody
  | TreeBody
  | EmbedBody
  | BlocksBody;
/** What a panel returns: a typed body, or any JSON object. */
export type PanelBody = TypedPanelBody | JsonObject;

/** The `type` of each typed body. */
export const PANEL_TYPES = ['tiles', 'table', 'columns', 'lines', 'heatmap', 'hbars', 'status_grid', 'note', 'code', 'tree', 'embed', 'blocks'] as const;

/** `body` as a typed body, or null when it is any other JSON object (a JSON tree). */
export function typedBody(body: unknown): TypedPanelBody | null {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  const type = (body as { type?: unknown }).type;
  return typeof type === 'string' && (PANEL_TYPES as readonly string[]).includes(type) ? (body as TypedPanelBody) : null;
}

/** A panel computed per run: a tab of each run, sent on its live feed (a trends panel is not). */
export const isRunPanel = (p: Pick<PanelInfo, 'scope'>): boolean => (p.scope ?? 'run') === 'run';
