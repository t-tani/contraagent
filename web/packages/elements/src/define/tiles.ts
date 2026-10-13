// Registers <cae-stat-tiles> and the <cae-count> it renders.
import { defineElement } from '../core/define.js';
import { CaeCount } from '../count/count.js';
import { CaeStatTiles } from '../tiles/stat-tiles.js';

defineElement('cae-stat-tiles', CaeStatTiles);
defineElement('cae-count', CaeCount);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeStatTiles, CaeCount };
export type { CaeEventMap } from '../core/events.js';
