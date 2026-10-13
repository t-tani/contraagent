// Registers <cae-json-tree>.
import { defineElement } from '../core/define.js';
import { CaeJsonTree } from '../json/json-tree.js';

defineElement('cae-json-tree', CaeJsonTree);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeJsonTree };
export type { CaeEventMap } from '../core/events.js';
