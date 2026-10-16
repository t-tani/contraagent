// Registers <cae-tree>.
import { defineElement } from '../core/define.js';
import { CaeTree } from '../tree/tree.js';

defineElement('cae-tree', CaeTree);

// The class, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeTree };
export type { CaeEventMap } from '../core/events.js';
