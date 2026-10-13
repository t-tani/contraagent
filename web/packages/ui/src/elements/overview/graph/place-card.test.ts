import { describe, expect, it } from 'vitest';
import { GAP, PAD, placeCard, type Box } from './place-card.js';

const frame: Box = { left: 0, top: 0, width: 1000, height: 400 };
const card = { width: 260, height: 180 };
const overlaps = (a: Box, b: Box) => a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height;
const cardBox = (p: { x: number; y: number }): Box => ({ left: p.x, top: p.y, ...card });
const inFrame = (b: Box) => b.left >= PAD && b.top >= PAD && b.left + b.width <= frame.width - PAD && b.top + b.height <= frame.height - PAD;

describe('placeCard', () => {
  it('goes right of the item, centred on it, with the pointer at its middle', () => {
    const item = { left: 100, top: 150, width: 120, height: 60 };
    const p = placeCard(item, frame, card);
    expect(p).toMatchObject({ shown: true, side: 'right', x: 220 + GAP });
    expect(p.y + p.arrow).toBe(180);
    expect(overlaps(cardBox(p), item)).toBe(false);
  });

  it('flips left at the frame’s right edge', () => {
    const item = { left: 860, top: 150, width: 120, height: 60 };
    const p = placeCard(item, frame, card);
    expect(p.side).toBe('left');
    expect(p.x + card.width).toBe(860 - GAP);
    expect(inFrame(cardBox(p))).toBe(true);
  });

  it('goes below when neither side has room, and above when below has none', () => {
    const wide = { left: 200, top: 10, width: 600, height: 60 };
    expect(placeCard(wide, frame, card).side).toBe('below');
    const low = { left: 200, top: 300, width: 600, height: 60 };
    const p = placeCard(low, frame, card);
    expect(p.side).toBe('above');
    expect(overlaps(cardBox(p), low)).toBe(false);
  });

  it('stays inside the frame near its corners', () => {
    for (const item of [
      { left: 0, top: 0, width: 14, height: 14 },
      { left: 986, top: 386, width: 14, height: 14 },
      { left: 0, top: 386, width: 14, height: 14 },
    ]) {
      const p = placeCard(item, frame, card);
      expect(inFrame(cardBox(p))).toBe(true);
      expect(overlaps(cardBox(p), item)).toBe(false);
    }
  });

  it('hides while the item is out of the frame', () => {
    expect(placeCard({ left: -200, top: 50, width: 100, height: 40 }, frame, card).shown).toBe(false);
    expect(placeCard({ left: 100, top: 420, width: 100, height: 40 }, frame, card).shown).toBe(false);
  });

  it('keeps clear of the node a mark is in, and points at the mark', () => {
    const node = { left: 100, top: 100, width: 160, height: 70 };
    const mark = { left: 230, top: 140, width: 14, height: 14 };
    const p = placeCard(node, frame, card, mark);
    expect(p.side).toBe('right');
    expect(p.x).toBe(260 + GAP);
    expect(p.y + p.arrow).toBe(147);
    expect(placeCard(node, frame, card, { ...mark, left: -40 }).shown).toBe(false);
  });

  it('keeps the pointer off the card’s corners', () => {
    const p = placeCard({ left: 100, top: 0, width: 14, height: 14 }, frame, card);
    expect(p.side).toBe('right');
    expect(p.arrow).toBeGreaterThanOrEqual(14);
  });
});
