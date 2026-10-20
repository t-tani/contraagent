// The generic graph's and mark matrix's words, as the pipeline graph says them.
import type { LayeredGraphStrings } from '@contraagent/elements/graph';
import type { MarkMatrixStrings } from '@contraagent/elements/matrix';
import { msg, str } from '@lit/localize';
import { listText } from '../../../words/format.js';
import { lineageWord } from '../../../words/lineage.js';

/**
 * Every word of the graph (`up`: Escape's hint without a selection, '' at the top;
 * `functions`: the layer has function nodes, so a row names a kind or a function); a
 * node always has its `progress`, so the words of a node's default count are not needed.
 */
export function graphStrings(up: boolean, functions: boolean): Omit<LayeredGraphStrings, 'progress'> {
  const enter = msg('Enter: open');
  return {
    graph: msg('Graph', { id: 'view-graph', desc: 'Button: show the pipeline as a graph' }),
    table: msg('Table', { id: 'view-table', desc: 'Button: show the pipeline as a table' }),
    view: msg('View'),
    zoomIn: msg('Zoom in'),
    zoomInTip: msg('Zoom in (Ctrl + scroll)'),
    zoomOut: msg('Zoom out'),
    zoomOutTip: msg('Zoom out (Ctrl + scroll)'),
    showAll: msg('Show all'),
    graphKeys: [msg('Tab: next node'), msg('Arrow keys: marks'), msg('Shift + arrow keys: earlier and later tasks'), enter],
    tableKeys: [msg('Tab: next row'), enter],
    matrixKeys: [msg('Arrow keys: marks'), enter],
    clearKey: msg('Esc: clear selection'),
    upKey: up ? msg('Esc: up a level') : '',
    inspector: msg('Selected item'),
    stubTip: msg('Outside this layer'),
    more: (n) => msg(str`+${n}`),
    badge: msg('number of passes'),
    solidEdge: lineageWord('given_from'),
    dottedEdge: lineageWord('after'),
    dashedEdge: lineageWord('created_from'),
    cycle: msg('next pass'),
    drill: msg('has a level below'),
    open: msg('Show inside'),
    close: msg('Hide inside'),
    iconNames: { agent: msg('agent task'), python: msg('Python task') },
    nameHeader: functions ? msg('Kind or function') : msg('Kind'),
    statusHeader: msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' }),
    solidHeader: msg('Given output of'),
    dottedHeader: msg('Runs after'),
    dashedHeader: msg('Created after'),
    laterHeader: msg('Later tasks'),
    none: msg('none', { id: 'none', desc: 'An empty value' }),
    inCluster: (label) => msg(str`${label} in the loop`),
    list: (items) => listText(items),
  };
}

/** The words of a loop's passes. */
export function matrixStrings(): MarkMatrixStrings {
  return { sortBy: msg('Sort units'), rowsHeader: msg('Unit') };
}
