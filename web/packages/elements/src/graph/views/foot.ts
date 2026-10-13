// The row under the frame: the legend, the zoom buttons and the view switch, and the keys of the view shown.
import { html, nothing, svg } from 'lit';
import { toneAttr } from '../../core/tone.js';
import { legend as legendRow, type LegendItem } from '../../primitives/legend.js';
import type { MarkMatrixInput } from '../../matrix/types.js';
import { asBar } from '../marks.js';
import { slotsOf, type GraphHost } from '../host.js';
import { innerIcon } from '../icons.js';

/** The legend on the left, the tools at the right end of the first line, and the keys under them while the graph has the focus. */
export function foot(h: GraphHost, matrix: MarkMatrixInput | null) {
  const table = !!matrix || h.asTable;
  return html`<div class="foot">
    ${legend(h, matrix)}
    <div class="tools">${table ? nothing : zoomTools(h)}${viewSwitch(h, table)}</div>
    <div class="keys">${keyHints(h, matrix).map((k, i) => html`${i ? ' | ' : ''}<span>${k}</span>`)}</div>
  </div>`;
}

/** Zoom out, zoom in, and back to the whole drawing (which does nothing while the whole drawing shows at its own size). */
function zoomTools(h: GraphHost) {
  const pz = h.pz;
  const w = h.strings;
  const whole = !pz.moved && pz.fitK >= 1;
  return html`<button type="button" aria-label=${w.zoomOut} title=${w.zoomOutTip} @click=${() => pz.zoomBy(1 / 1.25)}>−</button>
    <button type="button" aria-label=${w.zoomIn} title=${w.zoomInTip} @click=${() => pz.zoomBy(1.25)}>+</button>
    <button type="button" ?disabled=${whole} @click=${() => pz.showAll()}>${w.showAll}</button>`;
}

/** The two views, at the same place in each: the drawing, and the table (a mark matrix, or a row per node). */
function viewSwitch(h: GraphHost, table: boolean) {
  const options = [
    { value: 'graph', label: h.strings.graph },
    { value: 'table', label: h.strings.table },
  ];
  return html`<cae-segmented class="views" .options=${options} .value=${table ? 'table' : 'graph'} label=${h.strings.view}
    @cae-change=${(e: CustomEvent<{ value: string }>) => {
      e.stopPropagation();
      h.showView(e.detail.value === 'table' ? 'table' : 'graph');
    }}></cae-segmented>`;
}

/** The keys of the view shown. */
function keyHints(h: GraphHost, matrix: MarkMatrixInput | null): string[] {
  const w = h.strings;
  const esc = h.selected ? w.clearKey : w.upKey;
  const keys = matrix ? w.matrixKeys : h.asTable ? w.tableKeys : w.graphKeys;
  return [...keys, esc].filter(Boolean);
}

/** A status mark in a state's look, as the legend shows it. */
const legendMark = (h: GraphHost, state: string, badge?: string) => {
  const look = h.states[state];
  return html`<i class="mark" data-tone=${toneAttr(look?.tone)} data-shape=${look?.shape ?? nothing} data-n=${badge ?? nothing}></i>`;
};

/**
 * What the view shows that needs a word: the states of the marks shown, a badge when a
 * mark shows one, the icons the host names, the edge styles when both are drawn, a
 * cluster's return, and the mark of an item with an inner view.
 */
function legend(h: GraphHost, mx: MarkMatrixInput | null) {
  const g = h.graph;
  const flat = h.asTable && !mx;
  // The marks drawn: a node with a bar draws its failed marks only (its badges none); the table draws none.
  const marks = flat
    ? []
    : mx
      ? mx.rows.flatMap((r) => r.cells).map((m) => m && { state: m.state, badge: undefined })
      : g.nodes.flatMap((n) => slotsOf(n, g.series).map((s) => s && { state: s.m.state, badge: asBar(n, h.barAt) ? undefined : s.m.badge }));
  const shown = marks.filter((m): m is { state: string; badge: string | undefined } => m !== null);
  const present = new Set(shown.map((m) => m.state));
  const badge = shown.some((m) => m.badge);
  const dashed = !mx && !flat && [...g.edges, ...g.stubs].some((e) => e.style === 'dashed');
  const icons = new Set(mx ? mx.head.flat().flatMap((c) => c.icons ?? []) : g.nodes.flatMap((n) => n.icons ?? []));
  const cycles = !mx && !flat && g.clusters.some((c) => c.cycle);
  const inner = !mx && ((!flat && g.clusters.some((c) => c.drill)) || g.nodes.some((n) => n.drill));
  const first = Object.keys(h.states)[0] ?? '';
  const line = (dash: boolean) => svg`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${dash ? '5 4' : 'none'}></path></svg>`;
  const items: LegendItem[] = [
    ...Object.entries(h.states)
      .filter(([s]) => present.has(s))
      .map(([s, look]) => ({ label: look.label, icon: legendMark(h, s), decorative: true })),
    ...(badge ? [{ label: h.strings.badge, icon: legendMark(h, first, '2'), decorative: true }] : []),
    ...Object.entries(h.strings.iconNames)
      .filter(([name]) => icons.has(name))
      .map(([name, label]) => ({ label, icon: h.renderIcon(name) })),
    ...(dashed
      ? [
          { label: h.strings.solidEdge, icon: line(false) },
          { label: h.strings.dashedEdge, icon: line(true) },
        ]
      : []),
    ...(cycles
      ? [
          {
            label: h.strings.cycle,
            icon: html`<svg width="24" height="12" aria-hidden="true"><path class="ret" d="M20,1.5 V5.5 Q20,9.5 16,9.5 H8 Q4,9.5 4,5.5 V5"></path>
            <path class="ret-head" d="M4,0.8 L1.4,5 L6.6,5 z"></path></svg>`,
          },
        ]
      : []),
    ...(inner ? [{ label: h.strings.drill, icon: innerIcon() }] : []),
  ];
  return legendRow(items, { cls: 'big' });
}
