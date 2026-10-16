// Registers <cae-code>.
import { defineElement } from '../core/define.js';
import { CaeCode } from '../code/code.js';

defineElement('cae-code', CaeCode);

// The class, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeCode };
export type { CaeEventMap } from '../core/events.js';
