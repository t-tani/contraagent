// Registers <cae-lanes>.
import { defineElement } from '../core/define.js';
import { CaeLanes } from '../lanes/lanes.js';

defineElement('cae-lanes', CaeLanes);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeLanes };
export type { CaeEventMap } from '../core/events.js';
