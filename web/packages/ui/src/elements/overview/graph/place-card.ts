// Where the pipeline graph's inspector card goes: beside the selected item,
// inside the frame, never over the item. Pure: rectangles in, a position out.

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

export type Side = 'right' | 'left' | 'below' | 'above';

export interface Placement {
  /** The item is in view: the card shows. */
  shown: boolean;
  /** The card's corner, in the same coordinates as the boxes given. */
  x: number;
  y: number;
  /** The side of the item the card is on: its pointer is on the card's opposite edge. */
  side: Side;
  /** Where the pointer is along that edge, from the card's top (left, right) or left (below, above). */
  arrow: number;
  /** A side had room for the whole card: it covers none of the item. */
  fits: boolean;
}

/** The space between the item and the card (the pointer sits in it), and between the card and the frame's edge. */
export const GAP = 12;
export const PAD = 8;
/** The pointer keeps this far from the card's corners. */
const ARROW_INSET = 14;

const clamp = (v: number, lo: number, hi: number) => (hi < lo ? lo : Math.min(hi, Math.max(lo, v)));

/** The part of `a` inside `b`, or null when they do not meet. */
function within(a: Box, b: Box): Box | null {
  const left = Math.max(a.left, b.left);
  const top = Math.max(a.top, b.top);
  const right = Math.min(a.left + a.width, b.left + b.width);
  const bottom = Math.min(a.top + a.height, b.top + b.height);
  return right > left && bottom > top ? { left, top, width: right - left, height: bottom - top } : null;
}

/**
 * The card's place beside `item` within `frame`: right of it first, then left,
 * below and above, the first side with room for the whole card. When no side
 * has room, the side with the most, the card kept inside the frame (it may then
 * cover part of a large item). The card points at `aim` (a mark inside the item:
 * the card keeps clear of the whole node it is in) and hides while `aim` is
 * outside the frame.
 */
export function placeCard(item: Box, frame: Box, card: { width: number; height: number }, aim: Box = item): Placement {
  const seen = within(aim, frame);
  if (!seen) return { shown: false, x: 0, y: 0, side: 'right', arrow: 0, fits: false };
  const { width: w, height: h } = card;
  const fl = frame.left + PAD;
  const ft = frame.top + PAD;
  const fr = frame.left + frame.width - PAD;
  const fb = frame.top + frame.height - PAD;
  const ir = item.left + item.width;
  const ib = item.top + item.height;
  // Centred on the part of the item in view, kept in the frame.
  const cy = seen.top + seen.height / 2;
  const cx = seen.left + seen.width / 2;
  const yAt = clamp(cy - h / 2, ft, fb - h);
  const xAt = clamp(cx - w / 2, fl, fr - w);
  const room: Record<Side, number> = {
    right: fr - (ir + GAP) - w,
    left: item.left - GAP - w - fl,
    below: fb - (ib + GAP) - h,
    above: item.top - GAP - h - ft,
  };
  const order: Side[] = ['right', 'left', 'below', 'above'];
  const side = order.find((s) => room[s] >= 0) ?? order.reduce((a, b) => (room[b] > room[a] ? b : a));
  let x: number;
  let y: number;
  switch (side) {
    case 'right':
      [x, y] = [clamp(ir + GAP, fl, fr - w), yAt];
      break;
    case 'left':
      [x, y] = [clamp(item.left - GAP - w, fl, fr - w), yAt];
      break;
    case 'below':
      [x, y] = [xAt, clamp(ib + GAP, ft, fb - h)];
      break;
    case 'above':
      [x, y] = [xAt, clamp(item.top - GAP - h, ft, fb - h)];
      break;
  }
  const along = side === 'right' || side === 'left' ? clamp(cy - y, ARROW_INSET, h - ARROW_INSET) : clamp(cx - x, ARROW_INSET, w - ARROW_INSET);
  return { shown: true, x, y, side, arrow: along, fits: room[side] >= 0 };
}
