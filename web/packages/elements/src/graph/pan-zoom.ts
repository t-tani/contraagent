// The graph's frame: fit the drawing in it, zoom, and pan. The view is written on
// the stage directly, so panning and zooming do not render the element again.
import type { ReactiveController, ReactiveControllerHost } from 'lit';
import { FRAME_MIN, FRAME_SHARE } from '../core/frame.js';
import { fitView, zoomView, type View } from './view.js';

/** How far the view zooms: from half of the whole-drawing view (or of 1) up to this. */
export const ZOOM_MAX = 2.5;
/** A pointer moved this far is a pan, not a click. */
export const DRAG = 4;

/** The transform that shows `v`. */
export const transformOf = (v: View): string => `translate(${v.x}px,${v.y}px) scale(${v.k})`;

/** What there is to fit: the drawing's size, whether it runs top to bottom, and the least frame height (the selection's card). */
export interface Drawing {
  w: number;
  h: number;
  down: boolean;
  room: number;
}

export interface PanZoomOptions {
  /** The frame, and the stage in it that the view moves. */
  frame: () => HTMLElement | null;
  stage: () => HTMLElement | null;
  /** What to fit, or null while there is nothing to fit (a view without the drawing). */
  drawing: () => Drawing | null;
  /** Ctrl (or ⌘) and the wheel zoom: the drawing is shown. */
  wheel: () => boolean;
  /** The drawing runs top to bottom: a touch scrolls the page, a mouse still pans. */
  down: () => boolean;
  /** After the view moved. */
  onMove: () => void;
  /** After the host's size changed. */
  onResize: () => void;
}

/**
 * The zoom and pan of a drawing in its frame, and the frame's height. Until the
 * reader zooms or pans (`moved`), the view shows the whole drawing. The host
 * renders again only when what it draws changes: the frame's height, and whether
 * "Show all" does anything (`moved`, `fitK`).
 */
export class PanZoomController implements ReactiveController {
  /** The zoom and pan, written on the stage. */
  view: View = { k: 1, x: 0, y: 0 };
  /** The frame's height. */
  frameH = 0;
  /** The scale that shows the whole drawing. */
  fitK = 1;
  /** The reader has zoomed or panned away from the whole drawing. */
  moved = false;
  /** A pointer is down on the frame. */
  pressed = false;
  /** A pan in progress, and whether it went far enough to swallow the click that ends it. */
  private pan: { id: number; px: number; py: number; x: number; y: number; far: boolean } | null = null;
  private swallowClick = false;
  private resize?: ResizeObserver;

  constructor(
    private readonly host: ReactiveControllerHost & HTMLElement,
    private readonly o: PanZoomOptions,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    // Ctrl (or ⌘) and the wheel zoom; the wheel alone still scrolls the page.
    this.host.addEventListener('wheel', this.onWheel, { passive: false });
    this.host.addEventListener('click', this.onClickCapture, { capture: true });
  }

  hostDisconnected(): void {
    this.host.removeEventListener('wheel', this.onWheel);
    this.host.removeEventListener('click', this.onClickCapture, { capture: true });
    this.resize?.disconnect();
    this.resize = undefined;
  }

  hostUpdated(): void {
    if (this.resize) return;
    this.resize = new ResizeObserver(() => this.o.onResize());
    this.resize.observe(this.host);
  }

  /** The stage's style: the view, as the host renders it. */
  get transform(): string {
    return transformOf(this.view);
  }

  /** Back to the whole drawing, on a new layer. */
  reset(): void {
    this.moved = false;
  }

  /** The frame's height and, until the reader zooms or pans, the view of the whole drawing. */
  fit(): void {
    const d = this.o.drawing();
    if (!d) return;
    // The frame is beside the inspector, or above it on a narrow screen.
    const width = this.o.frame()?.clientWidth || this.host.clientWidth;
    // Top to bottom, the drawing is as tall as it needs at the frame's width.
    const whole = fitView(d.w, d.h, width, d.down ? Infinity : Math.max(FRAME_MIN, FRAME_SHARE * globalThis.innerHeight));
    if (whole.k !== this.fitK) {
      this.fitK = whole.k;
      this.host.requestUpdate();
    }
    // A short drawing's frame grows down to hold the selection's card; the drawing stays where it is.
    const h = d.down ? whole.h : Math.max(whole.h, d.room);
    if (!this.moved) {
      this.setHeight(h);
      if (whole.k !== this.view.k || whole.x !== this.view.x || whole.y !== this.view.y) this.setView({ k: whole.k, x: whole.x, y: whole.y });
    } else if (h > this.frameH) this.setHeight(h);
  }

  /** Back to the whole drawing. */
  showAll(): void {
    this.moved = false;
    this.fit();
    this.host.requestUpdate();
  }

  zoomBy(factor: number, cx = (this.o.frame()?.clientWidth ?? this.host.clientWidth) / 2, cy = this.frameH / 2): void {
    this.setMoved();
    this.setView(zoomView(this.view, factor, cx, cy, Math.min(1, this.fitK) / 2, ZOOM_MAX));
  }

  /** Bring `el` into the frame when zoom or pan left it outside. */
  reveal(el: HTMLElement): void {
    const frame = this.o.frame();
    if (!frame) return;
    const f = frame.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const pad = 24;
    let dx = 0;
    let dy = 0;
    if (r.left < f.left + pad) dx = f.left + pad - r.left;
    else if (r.right > f.right - pad) dx = f.right - pad - r.right;
    if (r.top < f.top + pad) dy = f.top + pad - r.top;
    else if (r.bottom > f.bottom - pad) dy = f.bottom - pad - r.bottom;
    if (dx || dy) {
      this.setMoved();
      this.setView({ ...this.view, x: this.view.x + dx, y: this.view.y + dy });
    }
  }

  readonly onPointerDown = (e: PointerEvent): void => {
    this.pressed = true;
    globalThis.addEventListener('pointerup', () => (this.pressed = false), { once: true });
    // On a narrow screen a touch scrolls the page; a mouse still pans.
    if (e.button !== 0 || (e.target as HTMLElement).closest('.tools') || (this.o.down() && e.pointerType !== 'mouse')) return;
    this.pan = { id: e.pointerId, px: e.clientX, py: e.clientY, x: this.view.x, y: this.view.y, far: false };
  };

  readonly onPointerMove = (e: PointerEvent): void => {
    const p = this.pan;
    if (!p || p.id !== e.pointerId) return;
    const dx = e.clientX - p.px;
    const dy = e.clientY - p.py;
    if (!p.far && Math.hypot(dx, dy) < DRAG) return;
    if (!p.far) {
      p.far = true;
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      (e.currentTarget as HTMLElement).classList.add('drag');
    }
    this.setMoved();
    this.setView({ ...this.view, x: p.x + dx, y: p.y + dy });
  };

  readonly onPointerUp = (e: PointerEvent): void => {
    const p = this.pan;
    if (!p || p.id !== e.pointerId) return;
    this.pan = null;
    (e.currentTarget as HTMLElement).classList.remove('drag');
    if (p.far) this.swallowClick = true;
  };

  private readonly onWheel = (e: WheelEvent): void => {
    if (!this.o.wheel() || !(e.ctrlKey || e.metaKey)) return;
    const frame = this.o.frame();
    if (!frame) return;
    e.preventDefault();
    const r = frame.getBoundingClientRect();
    this.zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  };

  /** The click that ends a pan opens nothing. */
  private readonly onClickCapture = (e: Event): void => {
    if (!this.swallowClick) return;
    this.swallowClick = false;
    e.stopPropagation();
    e.preventDefault();
  };

  private setMoved(): void {
    if (this.moved) return;
    this.moved = true;
    this.host.requestUpdate();
  }

  private setHeight(h: number): void {
    if (h === this.frameH) return;
    this.frameH = h;
    this.host.requestUpdate();
  }

  /** Write the view on the stage; the host's next render writes the same. */
  private setView(v: View): void {
    this.view = v;
    const stage = this.o.stage();
    if (stage) stage.style.transform = this.transform;
    this.o.onMove();
  }
}
