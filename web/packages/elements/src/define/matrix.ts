// Registers <cae-mark-matrix>.
import { defineElement } from '../core/define.js';
import { CaeMarkMatrix } from '../matrix/mark-matrix.js';

defineElement('cae-mark-matrix', CaeMarkMatrix);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeMarkMatrix };
export type { CaeEventMap } from '../core/events.js';
