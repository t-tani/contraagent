// @vitest-environment happy-dom
// The frame's zoom and pan: written on the stage, and the host renders again only
// when the frame's height or the "Show all" button changes.
import type { ReactiveControllerHost } from 'lit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DRAG, PanZoomController, transformOf, type Drawing } from './pan-zoom.js';

function setup(drawing: Drawing | null = { w: 1600, h: 400, down: false, room: 0 }) {
  const requestUpdate = vi.fn();
  const host = Object.assign(document.createElement('div'), {
    addController: vi.fn(),
    removeController: vi.fn(),
    requestUpdate,
    updateComplete: Promise.resolve(true),
  }) as unknown as ReactiveControllerHost & HTMLElement;
  Object.defineProperty(host, 'clientWidth', { value: 800 });
  const stage = document.createElement('div');
  const onMove = vi.fn();
  const pz = new PanZoomController(host, {
    frame: () => null,
    stage: () => stage,
    drawing: () => drawing,
    wheel: () => true,
    down: () => false,
    onMove,
    onResize: vi.fn(),
  });
  return { host, requestUpdate, stage, onMove, pz };
}

const pointer = (type: string, x: number, y: number, target: HTMLElement) =>
  ({ type, pointerId: 1, button: 0, pointerType: 'mouse', clientX: x, clientY: y, target, currentTarget: target }) as unknown as PointerEvent;

beforeEach(() => vi.stubGlobal('innerHeight', 1000));
afterEach(() => vi.unstubAllGlobals());

describe('PanZoomController', () => {
  it('writes the view as a transform', () => {
    expect(transformOf({ k: 0.5, x: 10, y: -4 })).toBe('translate(10px,-4px) scale(0.5)');
  });

  it('fits the whole drawing on the stage, without rendering for the view itself', () => {
    const { requestUpdate, stage, onMove, pz } = setup();
    pz.fit();
    expect(pz.view).toEqual({ k: 0.5, x: 0, y: 0 });
    expect(pz.frameH).toBe(200);
    expect(stage.style.transform).toBe(pz.transform);
    expect(onMove).toHaveBeenCalledTimes(1);
    // The height and the scale of the whole drawing changed: those are rendered.
    expect(requestUpdate).toHaveBeenCalledTimes(2);
    pz.fit();
    expect(requestUpdate).toHaveBeenCalledTimes(2);
    expect(onMove).toHaveBeenCalledTimes(1);
  });

  it('grows the frame for the card, and fits nothing without a drawing', () => {
    const short = setup({ w: 400, h: 100, down: false, room: 300 }).pz;
    short.fit();
    expect(short.frameH).toBe(300);
    expect(short.view).toEqual({ k: 1, x: 200, y: 0 });
    const none = setup(null).pz;
    none.fit();
    expect(none.frameH).toBe(0);
  });

  it('keeps a zoom across a fit, until "Show all"', () => {
    const { requestUpdate, pz } = setup();
    pz.fit();
    requestUpdate.mockClear();
    pz.zoomBy(2, 0, 0);
    expect(pz.moved).toBe(true);
    expect(pz.view.k).toBe(1);
    expect(requestUpdate).toHaveBeenCalledTimes(1);
    pz.zoomBy(2, 0, 0);
    expect(pz.view.k).toBe(2);
    expect(requestUpdate).toHaveBeenCalledTimes(1);
    pz.fit();
    expect(pz.view.k).toBe(2);
    pz.showAll();
    expect(pz.moved).toBe(false);
    expect(pz.view.k).toBe(0.5);
  });

  it('pans by dragging past the threshold, and swallows the click that ends it', () => {
    const { host, stage, pz } = setup();
    pz.fit();
    const frame = document.createElement('div');
    frame.setPointerCapture = vi.fn();
    pz.onPointerDown(pointer('pointerdown', 100, 100, frame));
    pz.onPointerMove(pointer('pointermove', 100 + DRAG - 1, 100, frame));
    expect(pz.moved).toBe(false);
    pz.onPointerMove(pointer('pointermove', 130, 90, frame));
    expect(pz.view).toEqual({ k: 0.5, x: 30, y: -10 });
    expect(stage.style.transform).toBe('translate(30px,-10px) scale(0.5)');
    expect(frame.classList.contains('drag')).toBe(true);
    pz.onPointerUp(pointer('pointerup', 130, 90, frame));
    expect(frame.classList.contains('drag')).toBe(false);
    pz.hostConnected();
    const click = new MouseEvent('click', { bubbles: true, cancelable: true });
    host.dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    const next = new MouseEvent('click', { bubbles: true, cancelable: true });
    host.dispatchEvent(next);
    expect(next.defaultPrevented).toBe(false);
    pz.hostDisconnected();
  });
});
