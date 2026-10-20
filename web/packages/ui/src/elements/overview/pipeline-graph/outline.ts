// The outline beside the pipeline graph: every function of the run's flow, and the loops
// they are in, as a tree, each with its tasks done of its tasks and what is not done. It
// shows the whole flow at once, whatever the graph draws open; the graph shows how its
// parts connect.
import { cycleIcon } from '@contraagent/elements/graph';
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import type { PlaceStats } from '../../../adapters/graph/compound.js';
import { shortName } from '../../../adapters/graph/flow-index.js';
import { LOOP_SEGMENT, type NodeCounts } from '../../../adapters/graph/types.js';
import { doneOf, exceptions, where } from '../../../adapters/graph/words.js';

/** An item of the outline: a function (its place) or a loop of the layer it is in. */
export interface OutlineItem {
  /** A function's place key; a loop's `<layer>|loop:<line>`. */
  id: string;
  type: 'fn' | 'loop';
  label: string;
  tip: string;
  /** The layer it is in (function names, outermost first). */
  layer: string[];
  /** A function: its name; a loop: its segment (`loop:12`, `loop:12.30`). */
  name: string;
  counts: NodeCounts;
  errors: boolean;
  kids: OutlineItem[];
  /**
   * The functions it stands for, outermost first: itself, then, for a chain of functions
   * each the only function in the layer of the one before, the rest of the chain (as the
   * graph draws it in one box). Going into it goes into the last.
   */
  parts: { id: string; layer: string[]; name: string }[];
}

const ZERO = (): NodeCounts => ({ total: 0, done: 0, partial: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, cancelled: 0 });

/** The outline of the flow: the places of `stats` (from the top of the flow) as a tree, a loop an item around the places in it. */
export function outlineTree(stats: ReadonlyMap<string, PlaceStats>): OutlineItem[] {
  const kidsOf = new Map<string | null, PlaceStats[]>();
  for (const s of stats.values()) (kidsOf.get(s.parent) ?? kidsOf.set(s.parent, []).get(s.parent))?.push(s);
  const build = (parent: string | null): OutlineItem[] => {
    const out: OutlineItem[] = [];
    const loops = new Map<string, OutlineItem>();
    for (const s of kidsOf.get(parent) ?? []) {
      const item: OutlineItem = {
        id: s.key,
        type: 'fn',
        label: shortName(s.name),
        tip: s.name,
        layer: s.layer,
        name: s.name,
        counts: s.counts,
        errors: s.errors,
        kids: build(s.key),
        parts: [{ id: s.key, layer: s.layer, name: s.name }],
      };
      // In a loop: inside the loop's item (a nested loop's inside its outer one).
      let into = out;
      s.loops.forEach((_, i) => {
        const seg = `${LOOP_SEGMENT}${s.loops.slice(0, i + 1).join('.')}`;
        const id = `${s.layer.join('/')}|${seg}`;
        let loop = loops.get(id);
        if (!loop) {
          const line = s.loops[i] as number;
          loop = { id, type: 'loop', label: msg(str`Loop at ${where(line, s.file)}`), tip: s.file ? `${s.file}:${line}` : '', layer: s.layer, name: seg, counts: ZERO(), errors: false, kids: [], parts: [{ id, layer: s.layer, name: seg }] };
          loops.set(id, loop);
          into.push(loop);
        }
        for (const k of Object.keys(loop.counts) as (keyof NodeCounts)[]) loop.counts[k] += s.counts[k];
        loop.errors ||= s.errors;
        into = loop.kids;
      });
      into.push(item);
    }
    return out;
  };
  return build(null);
}

/**
 * The items with each chain of single functions as one item named by its path (as the
 * graph draws it in one box): a function whose only item is a function, with no loop
 * between. A function on the way to the layer shown (`current`) stays an item of its own.
 */
export function chained(items: readonly OutlineItem[], current: (id: string) => boolean): OutlineItem[] {
  const chain = (it: OutlineItem): OutlineItem => {
    let x = it;
    while (x.type === 'fn' && !current(x.id) && x.kids.length === 1 && x.kids[0]?.type === 'fn' && !current(x.kids[0].id)) {
      const k = x.kids[0];
      x = { ...x, label: `${x.label} › ${k.label}`, tip: `${x.tip}\n${k.tip}`, kids: k.kids, parts: [...x.parts, ...k.parts] };
    }
    return { ...x, kids: x.kids.map(chain) };
  };
  return items.map(chain);
}

/** What the outline reads and does: which items are expanded, current or selected, and what a pick and Enter do. */
export interface OutlineHost {
  readonly live: boolean;
  expanded(id: string): boolean;
  expand(id: string, on: boolean): void;
  /** The item is on the way to the layer shown, or is it. */
  current(id: string): boolean;
  /** The item is the layer shown. */
  here(id: string): boolean;
  selected(id: string): boolean;
  /** Show the item in the graph, selected. */
  pick(item: OutlineItem): void;
  /** Go into the item: a function's layer, a loop's passes. */
  enter(item: OutlineItem): void;
}

/** The outline: a tree of buttons; a click shows an item in the graph, a double click or Enter goes into it. */
export function outline(h: OutlineHost, tree: readonly OutlineItem[]) {
  const items = chained(tree, (id) => h.current(id));
  const notesOf = (it: OutlineItem) => exceptions({ counts: it.counts, errors: it.errors ? 1 : 0 }, h.live);
  // A note only where it says something the item around it does not: where the problem narrows.
  const row = (it: OutlineItem, above = ''): unknown => {
    const open = it.kids.length > 0 && h.expanded(it.id);
    const c = it.counts;
    const pct = c.total ? Math.round(((c.done + c.partial + c.skipped) / c.total) * 100) : 0;
    const all = notesOf(it);
    const said = all.map(([, t]) => t).join('|');
    const notes = said === above ? [] : all;
    const cur = it.parts.some((p) => h.current(p.id));
    const here = it.parts.some((p) => h.here(p.id));
    return html`<li>
      <div class="orow ${cur ? 'cur' : ''} ${it.parts.some((p) => h.selected(p.id)) ? 'sel' : ''}">
        ${it.kids.length
          ? html`<button type="button" class="odisc" aria-expanded=${open} aria-label=${open ? msg(str`Fold ${it.label}`) : msg(str`Unfold ${it.label}`)}
              @click=${() => h.expand(it.id, !open)}><span aria-hidden="true">${open ? '▾' : '▸'}</span></button>`
          : html`<span class="odisc" aria-hidden="true"></span>`}
        <button type="button" class="oname" title=${it.tip || nothing} aria-current=${here ? 'location' : nothing}
          @click=${(e: MouseEvent) => e.detail < 2 && h.pick(it)} @dblclick=${() => h.enter(it)}
          @keydown=${(e: KeyboardEvent) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            h.enter(it);
          }}>
          ${it.type === 'loop' ? cycleIcon(12) : nothing}<span class="ol">${it.label}</span>
          <span class="obar" aria-hidden="true"><i style="width:${pct}%"></i></span>
          <span class="ocount" title=${doneOf(c)}>${c.done}/${c.total}</span>
        </button>
        ${notes.length ? html`<div class="onote">${notes.map(([cls, text]) => html`<span class=${cls}>${text}</span>`)}</div>` : nothing}
      </div>
      ${open ? html`<ul>${it.kids.map((k) => row(k, said))}</ul>` : nothing}
    </li>`;
  };
  return html`<nav class="outline" aria-label=${msg('Outline of the flow')}><ul class="otree">${items.map((it) => row(it))}</ul></nav>`;
}
