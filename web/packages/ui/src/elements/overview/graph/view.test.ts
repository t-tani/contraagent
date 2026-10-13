import { describe, expect, it } from 'vitest';
import { fitView, zoomView } from './view.js';

describe('fitView', () => {
  it('shows a small graph at its own size, centred, in a frame as tall as the graph', () => {
    expect(fitView(600, 200, 1200, 600)).toEqual({ k: 1, x: 300, y: 0, h: 200 });
  });

  it('scales a wide graph down to the frame width', () => {
    expect(fitView(2400, 400, 1200, 600)).toEqual({ k: 0.5, x: 0, y: 0, h: 200 });
  });

  it('scales a tall graph down to the frame height, and centres it', () => {
    const v = fitView(600, 2000, 1200, 500);
    expect(v.k).toBe(0.25);
    expect(v.h).toBe(500);
    expect(v.x).toBe((1200 - 150) / 2);
  });
});

describe('zoomView', () => {
  it('keeps the point under the cursor still, within the limits', () => {
    const v = zoomView({ k: 1, x: 0, y: 0 }, 2, 100, 50, 0.1, 4);
    expect(v).toEqual({ k: 2, x: -100, y: -50 });
    expect(zoomView({ k: 1, x: 0, y: 0 }, 10, 0, 0, 0.1, 4).k).toBe(4);
  });
});
