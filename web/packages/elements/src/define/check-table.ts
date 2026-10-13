// Registers <cae-check-table>.
import { defineElement } from '../core/define.js';
import { CaeCheckTable } from '../checks/check-table.js';

defineElement('cae-check-table', CaeCheckTable);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeCheckTable };
export type { CaeEventMap } from '../core/events.js';
