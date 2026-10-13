// The view of the drawing in its frame: fit and zoom.

/** A view of the graph: its scale and where its top left corner sits in the frame. */
export interface View {
  k: number;
  x: number;
  y: number;
}

/**
 * The frame's height and the view that shows the whole graph: scaled down to fit the
 * frame's width and at most `maxH` of height, never scaled up, and centred in a frame
 * at least `minH` tall.
 */
export function fitView(graphW: number, graphH: number, frameW: number, maxH: number, minH = 0): View & { h: number } {
  if (graphW <= 0 || graphH <= 0 || frameW <= 0) return { k: 1, x: 0, y: 0, h: Math.max(0, graphH) };
  const byWidth = Math.min(1, frameW / graphW);
  const h = Math.max(minH, Math.min(graphH * byWidth, maxH));
  const k = Math.min(byWidth, h / graphH);
  return { k, x: (frameW - graphW * k) / 2, y: (h - graphH * k) / 2, h };
}

/** `v` scaled by `factor` about the point (`cx`, `cy`) of the frame, within `min` and `max`. */
export function zoomView(v: View, factor: number, cx: number, cy: number, min: number, max: number): View {
  const k = Math.min(max, Math.max(min, v.k * factor));
  const r = k / v.k;
  return { k, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r };
}
