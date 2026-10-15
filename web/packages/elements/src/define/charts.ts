// Registers <cae-column-chart>, <cae-line-chart>, <cae-heatmap>, <cae-state-grid> and <cae-bar-chart>.
import { defineElement } from '../core/define.js';
import { CaeBarChart } from '../charts/bar-chart.js';
import { CaeColumnChart } from '../charts/column-chart.js';
import { CaeHeatmap } from '../charts/heatmap.js';
import { CaeLineChart } from '../charts/line-chart.js';
import { CaeStateGrid } from '../charts/state-grid.js';

defineElement('cae-column-chart', CaeColumnChart);
defineElement('cae-line-chart', CaeLineChart);
defineElement('cae-heatmap', CaeHeatmap);
defineElement('cae-state-grid', CaeStateGrid);
defineElement('cae-bar-chart', CaeBarChart);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeBarChart, CaeColumnChart, CaeHeatmap, CaeLineChart, CaeStateGrid };
export type { CaeEventMap } from '../core/events.js';
