// Registers <cae-data-table>.
import { defineElement } from '../core/define.js';
import { CaeDataTable } from '../table/data-table.js';

defineElement('cae-data-table', CaeDataTable);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeDataTable };
export type { CaeEventMap } from '../core/events.js';
