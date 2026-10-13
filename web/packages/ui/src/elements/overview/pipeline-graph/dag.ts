// A layer as a graph, in the frame that pans and zooms: loop boxes, nodes with their
// marks, stubs and edges; and the keys that move between marks and along edges.
import { msg, str } from '@lit/localize';
import { html, nothing, svg } from 'lit';
import { repeat } from 'lit/directives/repeat.js';
import { executorIcon } from '../../../words/executor.js';
import { facts } from '../../../words/format.js';
import { loopLabel, passCount, passSpread } from '../../../words/index.js';
import { isPoint } from '../graph/arrange.js';
import { related } from '../graph/highlight.js';
import type { Rect } from '../graph/layout.js';
import { asBar, barParts } from '../graph/marks.js';
import { alongEdge } from '../graph/nav.js';
import { edgePath, returnPath } from '../graph/paths.js';
import { markSel, selected } from '../graph/selection.js';
import type { GraphMark, GraphNode, LoopBox } from '../graph/types.js';
import { focusSelect, onNameKey, open, primary, select } from './actions.js';
import { BAR_LIST, causeOf, firstMark, gridOf, highlighted, slotsOf, type GraphHost, type MarkGroup } from './host.js';
import { innerIcon, loopIcon } from './icons.js';
import { LEGEND, countOf, doneOf, exceptions, markText, nodeLabel, nodeTip, stateCounts, where } from './words.js';

/** The graph in its frame: dragging pans, a click on the frame clears the selection. */
export function dag(h: GraphHost) {
  const pz = h.pz;
  return html`<div class="frame gframe ${h.down ? 'down' : ''}" style="height:${Math.round(pz.frameH)}px"
      @pointerdown=${pz.onPointerDown} @pointermove=${pz.onPointerMove} @pointerup=${pz.onPointerUp} @pointercancel=${pz.onPointerUp}
      @click=${(e: MouseEvent) => !(e.target as Element).closest('.node, .box, .stub, .tools') && select(h, '')}>
      <div class="stage view" style="transform:${pz.transform}">${graphView(h)}</div>
    </div>`;
}

/** Where an item is drawn, from its parent's corner (a loop box's, inside its border), or hidden until laid out. */
function at(h: GraphHost, id: string, parent: Rect | null): string {
  const r = h.lay?.at[id];
  if (!r) return 'left:0;top:0';
  const dx = parent ? parent.x + 1 : 0;
  const dy = parent ? parent.y + 1 : 0;
  return `left:${r.x - dx}px;top:${r.y - dy}px`;
}

function graphView(h: GraphHost) {
  const hl = highlighted(h);
  const on = hl === null ? null : related(h.plan.nodes, h.links, hl);
  const g = h.graph;
  const lay = h.lay;
  const nodes = new Map(g.nodes.map((n) => [n.id, n]));
  const boxes = new Map(g.boxes.map((b) => [b.id, b]));
  const stubs = new Map(g.stubs.map((s) => [s.id, s]));
  const items = (container: string): string[] => (g.slots[container] ?? []).flat().filter((id) => !isPoint(id));
  const item = (id: string, parent: Rect | null): unknown => {
    const b = boxes.get(id);
    if (b) return box(h, b, parent, (x, r) => item(x, r));
    const s = stubs.get(id);
    if (s) return html`<span class="stub" data-id=${s.id} style=${at(h, s.id, parent)} title=${msg('Outside this layer')}>${s.label}</span>`;
    const n = nodes.get(id);
    return n ? node(h, n, parent, on) : nothing;
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
      ${(lay?.edges ?? []).map((e) => svg`<path class=${e.type} d=${edgePath(e.runs, lay?.down)} marker-end="url(#arr)"></path>`)}
      ${(lay?.returns ?? []).map((r) => svg`<path class="ret" data-box=${r.box} d=${returnPath(r, lay?.down)} marker-end="url(#arr-ret)"></path>`)}
    </svg>
    ${repeat(items(''), (id) => id, (id) => item(id, null))}
  </div>`;
}

/** A click on a node or a box, not on one of its marks or on a node inside it: selects it. */
function onItemClick(h: GraphHost, e: MouseEvent, id: string): void {
  const own = (e.target as HTMLElement).closest('.mark, .taskchip, .node, .box');
  if (own !== e.currentTarget) return;
  e.stopPropagation();
  if (e.detail >= 2) return; // the second click of a double click
  select(h, id);
}

function onItemDblClick(h: GraphHost, e: MouseEvent, id: string): void {
  const own = (e.target as HTMLElement).closest('.mark, .taskchip, .node, .box');
  if (own !== e.currentTarget) return;
  e.stopPropagation();
  const s = selected(h.graph, h.matrix, id);
  if (s) primary(h, s);
}

function box(h: GraphHost, b: LoopBox, parent: Rect | null, item: (id: string, r: Rect | null) => unknown) {
  const r = h.lay?.at[b.id] ?? null;
  const at_ = msg(str`Loop at ${where(b.loop, b.file)}`);
  const spread = b.spread.length > 1 ? passSpread(b.spread) : '';
  const kids = (h.graph.slots[b.id] ?? []).flat().filter((id) => !isPoint(id));
  const size = r ? `;width:${r.w}px;height:${r.h}px` : '';
  return html`<section class="box ${h.sel === b.id ? 'sel' : ''}" role="group" data-box=${b.id} style=${at(h, b.id, parent) + size}
      aria-label=${facts(at_, passCount(b.passes), spread)}
      @click=${(e: MouseEvent) => onItemClick(h, e, b.id)} @dblclick=${(e: MouseEvent) => onItemDblClick(h, e, b.id)}>
    <div class="hd" data-id=${`lbl:${b.id}`}>
      <span class="line">
        <button type="button" class="name" title=${facts(loopLabel(), at_)} aria-pressed=${h.sel === b.id}
          @focus=${() => focusSelect(h, b.id)} @keydown=${(e: KeyboardEvent) => onNameKey(h, e, b.id)}>${loopIcon()}${loopLabel()}</button>
        <span class="count">${passCount(b.passes)}</span>
      </span>
      ${spread ? html`<span class="spread" title=${msg('Units by number of passes')}>${spread}</span>` : nothing}
    </div>
    <span class="cue" aria-hidden="true">${innerIcon()}</span>
    <div class="in">${repeat(kids, (id) => id, (id) => item(id, r))}</div>
  </section>`;
}

function node(h: GraphHost, n: GraphNode, parent: Rect | null, on: Set<string> | null) {
  const c = n.counts;
  // Finished (done and skipped) only sets the frame's look; the count is of the tasks done.
  const look = c.failed || n.errors ? 'fail' : c.running ? 'cur' : c.done + c.skipped === c.total ? 'done' : '';
  const bar = asBar(n);
  const group: MarkGroup = bar
    ? { id: n.id, label: n.label, slots: slotsOf(n).filter((m): m is GraphMark => m?.state === 'failed'), grid: { cols: BAR_LIST, size: 12, gap: 4 } }
    : { id: n.id, label: n.label, slots: slotsOf(n), grid: gridOf(n, h.graph.units.length) };
  const ex = exceptions(n, h.live);
  const on_ = h.sel === n.id;
  const icons = n.executor === 'mixed' ? html`${executorIcon(false)}${executorIcon(true)}` : n.executor ? executorIcon(n.executor === 'python') : nothing;
  return html`<section class="node ${n.type} ${n.executor === 'agent' ? 'agent' : ''} ${look} ${on_ ? 'sel' : ''}" role="group" data-id=${n.id}
    aria-label=${nodeLabel(n, h.graph, h.live)}
    style="${at(h, n.id, parent)};--cols:${group.grid.cols};--m:${group.grid.size}px;--g:${group.grid.gap}px"
    @click=${(e: MouseEvent) => onItemClick(h, e, n.id)} @dblclick=${(e: MouseEvent) => onItemDblClick(h, e, n.id)}>
    <div class="hd">
      <span class="nm">${icons}<button type="button" class="name" title=${nodeTip(n)} aria-pressed=${on_}
        @focus=${() => focusSelect(h, n.id)} @keydown=${(e: KeyboardEvent) => onNameKey(h, e, n.id)}>${n.label}</button></span>
      <span class="right"><span class="count" aria-hidden="true" title=${doneOf(c)}>${c.done}/${c.total}</span>${n.type === 'flow'
        ? html`<span class="cue" aria-hidden="true">${innerIcon()}</span>`
        : nothing}</span>
    </div>
    ${bar ? statusBar(h, n, group, on) : marks(h, group, on)}
    ${ex.length ? html`<div class="ex" aria-hidden="true">${ex.map(([cls, t]) => html`<span class=${cls}>${t}</span>`)}</div>` : nothing}
  </section>`;
}

/** A node with too many marks to draw: a bar of its counts, and its failed marks by name. */
function statusBar(h: GraphHost, n: GraphNode, g: MarkGroup, on: Set<string> | null) {
  const parts = barParts(n.counts, LEGEND);
  const shown = g.slots.slice(0, BAR_LIST);
  const more = g.slots.length - shown.length;
  const active = Math.min(h.active.get(g.id) ?? 0, Math.max(0, shown.length - 1));
  return html`<div class="sbar" role="img" aria-label=${stateCounts(n.counts, h.live)}>
      ${parts.map((p) => html`<i class=${p.state} style="width:${p.pct}%" title=${countOf(p.state, p.n, h.live)}></i>`)}
    </div>
    ${shown.length
      ? html`<div class="fails" @keydown=${(e: KeyboardEvent) => onKey(h, e, { ...g, slots: shown, grid: { ...g.grid, cols: shown.length } })}>
          ${shown.map((m, i) => (m ? mark(h, g, m, i, i === active, on, true) : nothing))}
          ${more > 0 ? html`<span>${msg(str`+${more}`)}</span>` : nothing}
        </div>`
      : nothing}`;
}

/** A group's marks, with one tab stop. */
function marks(h: GraphHost, g: MarkGroup, on: Set<string> | null) {
  const active = Math.min(h.active.get(g.id) ?? firstMark(g.slots), g.slots.length - 1);
  return html`<div class="marks ${g.grid.size >= 10 ? 'big' : ''}" @keydown=${(e: KeyboardEvent) => onKey(h, e, g)}>
    ${g.slots.map((m, i) => (m ? mark(h, g, m, i, i === active, on) : html`<span class="slot"></span>`))}
  </div>`;
}

function mark(h: GraphHost, g: MarkGroup, m: GraphMark, i: number, tabStop: boolean, on: Set<string> | null, chip = false) {
  const { name, parts } = markText(g.label, m, { task: h.links.byKey.get(m.key), causeOf: (k) => causeOf(h, k), live: h.live });
  const hlKey = m.unit || m.key;
  const lit = on !== null && ((m.unit !== '' && m.unit === highlighted(h)) || m.keys.some((k) => on.has(k)));
  const id = markSel(g.id, m);
  const sel = h.sel === id ? 'sel' : '';
  const focus = (e: FocusEvent) => {
    h.hover = hlKey;
    h.active.set(g.id, i);
    h.pz.reveal(e.currentTarget as HTMLElement);
    focusSelect(h, id);
  };
  // The tooltip names it and its status; the rest is in the inspector.
  const tip = [name, parts[0] ?? ''].filter(Boolean).join('\n');
  if (chip) {
    return html`<button type="button" class="taskchip ${lit ? 'on' : ''} ${sel}" data-i=${i} tabindex=${tabStop ? 0 : -1}
      title=${tip} aria-label=${facts(name, ...parts)} aria-pressed=${!!sel}
      @mouseenter=${() => (h.hover = hlKey)} @focus=${focus} @blur=${() => (h.hover = null)}
      @click=${() => select(h, id)} @dblclick=${() => open(h, m)}>${m.unit || m.key}</button>`;
  }
  return html`<button type="button" class="mark ${m.state} ${lit ? 'on' : ''} ${sel}" data-i=${i} data-n=${m.passes ?? nothing} tabindex=${tabStop ? 0 : -1}
    title=${tip}
    aria-label=${facts(name, ...parts)} aria-pressed=${!!sel}
    @mouseenter=${() => (h.hover = hlKey)}
    @focus=${focus}
    @blur=${() => (h.hover = null)}
    @click=${() => select(h, id)}
    @dblclick=${() => open(h, m)}></button>`;
}

/** Arrow keys, Home and End within a group's marks, skipping empty slots; Shift and an arrow key along an edge to another node. */
function onKey(h: GraphHost, e: KeyboardEvent, g: MarkGroup): void {
  const target = e.target as HTMLElement;
  if (!target.classList.contains('mark') && !target.classList.contains('taskchip')) return;
  if (e.shiftKey && e.key.startsWith('Arrow')) return toEdge(h, e, g);
  const { slots } = g;
  if (e.key === 'Enter') {
    const m = slots[Number(target.dataset['i'])];
    e.preventDefault();
    if (m) open(h, m);
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
  h.el.requestUpdate();
  const group = e.currentTarget as HTMLElement;
  void h.el.updateComplete.then(() => group.querySelector<HTMLElement>(`[data-i="${next}"]`)?.focus());
}

/** To the node an edge joins: a later one (Shift and → or ↓) or an earlier one (Shift and ← or ↑), on the same unit when it has a mark there. */
function toEdge(h: GraphHost, e: KeyboardEvent, g: MarkGroup): void {
  const dir = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 'later' : 'earlier';
  const lay = h.lay;
  const across = (id: string) => {
    const r = lay?.at[id];
    return !r ? 0 : lay?.down ? r.x + r.w / 2 : r.y + r.h / 2;
  };
  const to = alongEdge(h.graph, g.id, dir, across);
  e.preventDefault();
  if (!to) return;
  const n = h.graph.nodes.find((x) => x.id === to);
  if (!n) return;
  const unit = g.slots[h.active.get(g.id) ?? firstMark(g.slots)]?.unit ?? '';
  const slots = asBar(n) ? slotsOf(n).filter((m) => m?.state === 'failed') : slotsOf(n);
  const same = unit ? slots.findIndex((m) => m?.unit === unit) : -1;
  const i = same >= 0 ? same : (h.active.get(n.id) ?? firstMark(slots));
  h.active.set(n.id, i);
  h.el.requestUpdate();
  void h.el.updateComplete.then(() => {
    const el = h.root.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(to)}"]`);
    (el?.querySelector<HTMLElement>(`[data-i="${i}"]`) ?? el?.querySelector<HTMLElement>('.name'))?.focus();
  });
}
