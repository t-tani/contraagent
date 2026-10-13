// The graph in the frame that pans and zooms: clusters, nodes with their marks,
// stubs and edges; and the keys that move between marks and along edges.
import { html, nothing, svg } from 'lit';
import { repeat } from 'lit/directives/repeat.js';
import { toneAttr, type Tone } from '../../core/tone.js';
import { stateCount } from '../../primitives/states.js';
import { isPoint } from '../arrange.js';
import { BAR_LIST, firstMark, gridOf, hlKeyOf, slotsOf, type GraphHost, type MarkGroup, type Slot } from '../host.js';
import { cycleIcon, innerIcon } from '../icons.js';
import type { Rect } from '../layout.js';
import { asBar, barParts } from '../marks.js';
import { alongEdge } from '../nav.js';
import { edgePath, returnPath } from '../paths.js';
import type { GraphClusterInput, GraphNode } from '../types.js';

/** A note's class by its tone: failed, attention, running, muted. */
export const NOTE_CLASS: Partial<Record<Tone, string>> = { failed: 'err', attention: 'warn', running: 'live', muted: 'mut' };

/** The graph in its frame: dragging pans, a click on the frame clears the selection. */
export function dag(h: GraphHost) {
  const pz = h.pz;
  return html`<div class="frame gframe ${h.down ? 'down' : ''}" part="frame" style="height:${Math.round(pz.frameH)}px"
      @pointerdown=${pz.onPointerDown} @pointermove=${pz.onPointerMove} @pointerup=${pz.onPointerUp} @pointercancel=${pz.onPointerUp}
      @click=${(e: MouseEvent) => !(e.target as Element).closest('.node, .cluster, .stub, .tools') && h.select(null)}>
      <div class="stage view" part="stage" style="transform:${pz.transform}">${graphView(h)}</div>
    </div>`;
}

/** Where an item is drawn, from its parent's corner (a cluster's, inside its border), or hidden until laid out. */
function at(h: GraphHost, id: string, parent: Rect | null): string {
  const r = h.lay?.at[id];
  if (!r) return 'left:0;top:0';
  const dx = parent ? parent.x + 1 : 0;
  const dy = parent ? parent.y + 1 : 0;
  return `left:${r.x - dx}px;top:${r.y - dy}px`;
}

function graphView(h: GraphHost) {
  const { on } = h.lit();
  const g = h.drawn;
  const lay = h.lay;
  const stubs = new Map(g.stubs.map((s) => [s.id, s]));
  const items = (container: string): string[] => (h.arr.slots[container] ?? []).flat().filter((id) => !isPoint(id));
  const item = (id: string, parent: Rect | null): unknown => {
    const b = h.clusters.get(id);
    if (b) return cluster(h, b, parent, (x, r) => item(x, r));
    const s = stubs.get(id);
    if (s) return html`<span class="stub" part="stub" data-id=${s.id} style=${at(h, s.id, parent)} title=${h.words.stubTip}>${s.label}</span>`;
    const n = h.nodes.get(id);
    return n ? node(h, n, parent) : nothing;
  };
  // Unplaced until a layout of this structure exists: the first render only measures.
  const placed = !!lay && g.nodes.every((n) => lay.at[n.id]);
  const w = lay?.w ?? 0;
  const ht = lay?.h ?? 0;
  return html`<div class="dag ${h.down ? 'down' : ''} ${on ? 'hl' : ''} ${placed ? '' : 'unplaced'}" style="width:${w}px;height:${ht}px"
    @mouseleave=${() => (h.hover = null)}>
    <svg class="edges" aria-hidden="true" width=${w} height=${ht}>
      <defs>
        <marker id="arr" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
          <path d="M0,0.5 L8,4 L0,7.5 z" fill="var(--line2)" stroke="none"></path>
        </marker>
        <marker id="arr-ret" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
          <path class="ret-tip" d="M0,0.5 L8,4 L0,7.5 z"></path>
        </marker>
      </defs>
      ${(lay?.edges ?? []).map((e) => svg`<path class=${e.style} part="edge" d=${edgePath(e.runs, lay?.down)} marker-end="url(#arr)"></path>`)}
      ${(lay?.returns ?? []).map((r) => svg`<path class="ret" data-cluster=${r.box} d=${returnPath(r, lay?.down)} marker-end="url(#arr-ret)"></path>`)}
    </svg>
    ${repeat(items(''), (id) => id, (id) => item(id, null))}
  </div>`;
}

/** A click on a node or a cluster, not on one of its marks or on a node inside it: selects it. */
function onItemClick(h: GraphHost, e: MouseEvent, id: string): void {
  const own = (e.target as HTMLElement).closest('.mark, .taskchip, .node, .cluster');
  if (own !== e.currentTarget) return;
  e.stopPropagation();
  if (e.detail >= 2) return; // the second click of a double click
  h.select(id);
}

function onItemDblClick(h: GraphHost, e: MouseEvent, id: string): void {
  const own = (e.target as HTMLElement).closest('.mark, .taskchip, .node, .cluster');
  if (own !== e.currentTarget) return;
  e.stopPropagation();
  h.act(id);
}

/** Enter on a node's or a cluster's name: its action (Space selects it, as a click does). */
function onNameKey(h: GraphHost, e: KeyboardEvent, id: string): void {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  h.act(id);
}

function cluster(h: GraphHost, b: GraphClusterInput, parent: Rect | null, item: (id: string, r: Rect | null) => unknown) {
  const r = h.lay?.at[b.id] ?? null;
  const kids = (h.arr.slots[b.id] ?? []).flat().filter((id) => !isPoint(id));
  const size = r ? `;width:${r.w}px;height:${r.h}px` : '';
  const sel = h.selected === b.id;
  return html`<section class="cluster ${sel ? 'sel' : ''}" part="cluster" role="group" data-cluster=${b.id} style=${at(h, b.id, parent) + size}
      aria-label=${b.summary ?? b.label}
      @click=${(e: MouseEvent) => onItemClick(h, e, b.id)} @dblclick=${(e: MouseEvent) => onItemDblClick(h, e, b.id)}>
    <div class="hd" part="cluster-label" data-id=${`lbl:${b.id}`}>
      <span class="line">
        <button type="button" class="name" title=${b.tip ?? nothing} aria-pressed=${sel}
          @focus=${() => h.focusSelect(b.id)} @keydown=${(e: KeyboardEvent) => onNameKey(h, e, b.id)}>${b.cycle ? cycleIcon() : nothing}${b.label}</button>
        ${b.note ? html`<span class="count">${b.note}</span>` : nothing}
      </span>
      ${b.detail ? html`<span class="spread" title=${b.detailTip ?? nothing}>${b.detail}</span>` : nothing}
    </div>
    ${b.drill ? html`<span class="cue" aria-hidden="true">${innerIcon()}</span>` : nothing}
    <div class="in">${repeat(kids, (id) => id, (id) => item(id, r))}</div>
  </section>`;
}

/** A node's notes ("1 failed | 1 not started"), each in its tone's class. */
export const notes = (n: GraphNode, tag: 'span' | 'div' = 'span') =>
  (n.notes ?? []).map((f) => (tag === 'span' ? html`<span class=${NOTE_CLASS[f.tone ?? 'neutral'] ?? ''}>${f.text}</span>` : html`<div class=${NOTE_CLASS[f.tone ?? 'neutral'] ?? ''}>${f.text}</div>`));

function node(h: GraphHost, n: GraphNode, parent: Rect | null) {
  const series = h.drawn.series;
  const bar = asBar(n, h.barAt);
  const all = slotsOf(n, series);
  const failed = (s: Slot | null): s is Slot => !!s && h.states[s.m.state]?.tone === 'failed';
  const group: MarkGroup = bar
    ? { id: n.id, slots: all.filter(failed), grid: { cols: BAR_LIST, size: 12, gap: 4 } }
    : { id: n.id, slots: all, grid: gridOf(n, series.length) };
  const sel = h.selected === n.id;
  const icons = (n.icons ?? []).map((x) => h.renderIcon(x));
  return html`<section class="node ${n.drill ? 'drill' : ''} ${n.accent ? 'accent' : ''} ${sel ? 'sel' : ''}" part="node" role="group" data-id=${n.id}
    data-look=${n.look && n.look !== 'neutral' ? n.look : nothing} aria-label=${n.summary ?? n.label}
    style="${at(h, n.id, parent)};--cols:${group.grid.cols};--m:${group.grid.size}px;--g:${group.grid.gap}px"
    @click=${(e: MouseEvent) => onItemClick(h, e, n.id)} @dblclick=${(e: MouseEvent) => onItemDblClick(h, e, n.id)}>
    <div class="hd" part="node-header">
      <span class="nm">${icons}<button type="button" class="name" part="node-name" title=${n.tip ?? nothing} aria-pressed=${sel}
        @focus=${() => h.focusSelect(n.id)} @keydown=${(e: KeyboardEvent) => onNameKey(h, e, n.id)}>${n.label}</button></span>
      <span class="right"><span class="count" aria-hidden="true" title=${n.progress.label}>${n.progress.done}/${n.progress.total}</span>${n.drill
        ? html`<span class="cue" aria-hidden="true">${innerIcon()}</span>`
        : nothing}</span>
    </div>
    ${bar ? statusBar(h, n, group) : marks(h, group)}
    ${n.notes?.length ? html`<div class="ex" aria-hidden="true">${notes(n)}</div>` : nothing}
  </section>`;
}

/** A node with too many marks to draw: a bar of its counts, and its failed marks by name. */
function statusBar(h: GraphHost, n: GraphNode, g: MarkGroup) {
  const order = Object.keys(h.states);
  const parts = barParts(n.counts, order);
  const shown = g.slots.slice(0, BAR_LIST);
  const more = g.slots.length - shown.length;
  const active = Math.min(h.active.get(g.id) ?? 0, Math.max(0, shown.length - 1));
  const words = order.filter((s) => n.counts[s]).map((s) => stateCount(h.states, s, n.counts[s] ?? 0));
  return html`<div class="sbar" role="img" aria-label=${words.join(' | ')}>
      ${parts.map((p) => {
        const look = h.states[p.state];
        return html`<i data-tone=${toneAttr(look?.tone)} data-shape=${look?.shape ?? nothing} style="width:${p.pct}%" title=${stateCount(h.states, p.state, p.n)}></i>`;
      })}
    </div>
    ${shown.length
      ? html`<div class="fails" @keydown=${(e: KeyboardEvent) => onKey(h, e, { ...g, slots: shown, grid: { ...g.grid, cols: shown.length } })}>
          ${shown.map((s, i) => (s ? mark(h, g, s, i, i === active, true) : nothing))}
          ${more > 0 ? html`<span>${h.words.more(more)}</span>` : nothing}
        </div>`
      : nothing}`;
}

/** A group's marks, with one tab stop. */
function marks(h: GraphHost, g: MarkGroup) {
  const active = Math.min(h.active.get(g.id) ?? firstMark(g.slots), g.slots.length - 1);
  return html`<div class="marks ${g.grid.size >= 10 ? 'big' : ''}" @keydown=${(e: KeyboardEvent) => onKey(h, e, g)}>
    ${g.slots.map((s, i) => (s ? mark(h, g, s, i, i === active) : html`<span class="slot"></span>`))}
  </div>`;
}

function mark(h: GraphHost, g: MarkGroup, s: Slot, i: number, tabStop: boolean, chip = false) {
  const { m } = s;
  const { key, on } = h.lit();
  const hlKey = hlKeyOf(s);
  const lit = on !== null && ((s.series !== '' && s.series === key) || on.has(m.id));
  const sel = h.selected === m.id ? 'sel' : '';
  const focus = (e: FocusEvent) => {
    h.hover = hlKey;
    h.active.set(g.id, i);
    h.pz.reveal(e.currentTarget as HTMLElement);
    h.focusSelect(m.id);
  };
  if (chip) {
    return html`<button type="button" class="taskchip ${lit ? 'on' : ''} ${sel}" part="mark" data-i=${i} tabindex=${tabStop ? 0 : -1}
      title=${m.tip ?? nothing} aria-label=${m.label} aria-pressed=${!!sel}
      @mouseenter=${() => (h.hover = hlKey)} @focus=${focus} @blur=${() => (h.hover = null)}
      @click=${() => h.select(m.id)} @dblclick=${() => h.act(m.id)}>${m.name ?? (s.series || m.id)}</button>`;
  }
  const look = h.states[m.state];
  return html`<button type="button" class="mark ${lit ? 'on' : ''} ${sel}" part="mark" data-tone=${toneAttr(look?.tone)} data-shape=${look?.shape ?? nothing}
    data-i=${i} data-n=${m.badge ?? nothing} tabindex=${tabStop ? 0 : -1}
    title=${m.tip ?? nothing}
    aria-label=${m.label} aria-pressed=${!!sel}
    @mouseenter=${() => (h.hover = hlKey)}
    @focus=${focus}
    @blur=${() => (h.hover = null)}
    @click=${() => h.select(m.id)}
    @dblclick=${() => h.act(m.id)}></button>`;
}

/** Arrow keys, Home and End within a group's marks, skipping empty slots; Shift and an arrow key along an edge to another node. */
function onKey(h: GraphHost, e: KeyboardEvent, g: MarkGroup): void {
  const target = e.target as HTMLElement;
  if (!target.classList.contains('mark') && !target.classList.contains('taskchip')) return;
  if (e.shiftKey && e.key.startsWith('Arrow')) return toEdge(h, e, g);
  const { slots } = g;
  if (e.key === 'Enter') {
    const s = slots[Number(target.dataset['i'])];
    e.preventDefault();
    if (s) h.act(s.m.id);
    return;
  }
  const cur = h.active.get(g.id) ?? firstMark(slots);
  const step: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: g.grid.cols, ArrowUp: -g.grid.cols };
  let next: number;
  if (e.key === 'Home') next = firstMark(slots);
  else if (e.key === 'End') next = slots.length - 1 - [...slots].reverse().findIndex((m) => m !== null);
  else if (step[e.key] !== undefined) {
    const d = step[e.key] as number;
    next = cur + d;
    while (next >= 0 && next < slots.length && !slots[next]) next += Math.sign(d);
    if (next < 0 || next >= slots.length) return;
  } else return;
  e.preventDefault();
  h.active.set(g.id, next);
  h.requestUpdate();
  const group = e.currentTarget as HTMLElement;
  void h.updateComplete.then(() => group.querySelector<HTMLElement>(`[data-i="${next}"]`)?.focus());
}

/** To the node an edge joins: a later one (Shift and → or ↓) or an earlier one (Shift and ← or ↑), on the same series when it has a mark there. */
function toEdge(h: GraphHost, e: KeyboardEvent, g: MarkGroup): void {
  const dir = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 'later' : 'earlier';
  const lay = h.lay;
  const across = (id: string) => {
    const r = lay?.at[id];
    return !r ? 0 : lay?.down ? r.x + r.w / 2 : r.y + r.h / 2;
  };
  const to = alongEdge({ drawn: h.arr.drawn, edges: h.drawn.edges, back: h.arr.back }, g.id, dir, across);
  e.preventDefault();
  if (!to) return;
  const n = h.nodes.get(to);
  if (!n) return;
  const series = g.slots[h.active.get(g.id) ?? firstMark(g.slots)]?.series ?? '';
  const all = slotsOf(n, h.drawn.series);
  const slots = asBar(n, h.barAt) ? all.filter((s) => !!s && h.states[s.m.state]?.tone === 'failed') : all;
  const same = series ? slots.findIndex((s) => s?.series === series) : -1;
  const i = same >= 0 ? same : (h.active.get(n.id) ?? firstMark(slots));
  h.active.set(n.id, i);
  h.requestUpdate();
  void h.updateComplete.then(() => {
    const el = h.renderRoot.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(to)}"]`);
    (el?.querySelector<HTMLElement>(`[data-i="${i}"]`) ?? el?.querySelector<HTMLElement>('.name'))?.focus();
  });
}
