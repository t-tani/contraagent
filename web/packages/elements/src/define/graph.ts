// Registers <cae-layered-graph>, and the elements it renders: <cae-mark-matrix> and <cae-segmented>.
import { defineElement } from '../core/define.js';
import { CaeLayeredGraph } from '../graph/layered-graph.js';
import './matrix.js';
import './segmented.js';

defineElement('cae-layered-graph', CaeLayeredGraph);
