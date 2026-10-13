// The words for what the view shows.
import { legend as legendRow, type LegendItem } from '@contraagent/elements/primitives';
import { msg } from '@lit/localize';
import { html, svg } from 'lit';
import { executorIcon } from '../../../words/executor.js';
import { asBar } from '../graph/marks.js';
import type { GraphMark } from '../graph/types.js';
import { slotsOf, type GraphHost } from './host.js';
import { innerIcon } from './icons.js';
import { LEGEND, stateWord } from './words.js';

/**
 * What the view shows that needs a word: the states of the marks shown, the pass number
 * when a mark shows one, who runs the kind nodes' tasks, the kinds of edges when there is
 * more than one, a loop's return to its next pass, and the mark of a node or a box with an
 * inner view.
 */
export function legend(h: GraphHost) {
  const mx = h.matrix;
  const g = h.graph;
  const flat = h.asTable && !mx;
  // The marks drawn: a node with a bar draws its failed marks only; the table draws none.
  const marks = flat
    ? []
    : mx
      ? mx.rows.flatMap((r) => r.cells)
      : g.nodes.flatMap((n) => (asBar(n) ? slotsOf(n).map((m) => m && { ...m, passes: undefined }) : slotsOf(n)));
  const shown = marks.filter((m): m is GraphMark => m !== null);
  const present = new Set(shown.map((m) => m.state));
  const passes = !mx && shown.some((m) => m.passes);
  const created = !mx && !flat && [...g.edges, ...g.stubs].some((e) => e.type === 'created');
  const nodes = mx ? mx.columns.map((c) => c.node) : g.nodes;
  const ex = new Set(nodes.flatMap((n) => (n.executor === 'mixed' ? ['agent', 'python'] : n.executor ? [n.executor] : [])));
  const loops = !mx && !flat && g.boxes.length > 0;
  const inner = !mx && (loops || g.nodes.some((n) => n.type === 'flow'));
  const line = (dash: boolean) => svg`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${dash ? '5 4' : 'none'}></path></svg>`;
  const items: LegendItem[] = [
    ...LEGEND.filter((s) => present.has(s)).map((s) => ({ label: stateWord(s, h.live), icon: html`<i class="mark ${s}"></i>`, decorative: true })),
    ...(passes ? [{ label: msg('number of passes'), icon: html`<i class="mark done" data-n="2"></i>`, decorative: true }] : []),
    ...(ex.has('agent') ? [{ label: msg('agent task'), icon: executorIcon(false) }] : []),
    ...(ex.has('python') ? [{ label: msg('Python task'), icon: executorIcon(true) }] : []),
    ...(created
      ? [
          { label: msg('waits for output'), icon: line(false) },
          { label: msg('created after result'), icon: line(true) },
        ]
      : []),
    ...(loops
      ? [
          {
            label: msg('next pass'),
            icon: html`<svg width="24" height="12" aria-hidden="true"><path class="ret" d="M20,1.5 V5.5 Q20,9.5 16,9.5 H8 Q4,9.5 4,5.5 V5"></path>
            <path class="ret-head" d="M4,0.8 L1.4,5 L6.6,5 z"></path></svg>`,
          },
        ]
      : []),
    ...(inner ? [{ label: msg('has an inner view'), icon: innerIcon() }] : []),
  ];
  return legendRow(items, { cls: 'big' });
}
