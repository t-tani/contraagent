// Registers <cae-segmented>.
import { defineElement } from '../core/define.js';
import { CaeSegmented } from '../primitives/segmented.js';

defineElement('cae-segmented', CaeSegmented);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeSegmented };
export type { CaeEventMap } from '../core/events.js';
