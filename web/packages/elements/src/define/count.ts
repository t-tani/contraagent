// Registers <cae-count> and <cae-elapsed>.
import { defineElement } from '../core/define.js';
import { CaeCount } from '../count/count.js';
import { CaeElapsed } from '../count/elapsed.js';

defineElement('cae-count', CaeCount);
defineElement('cae-elapsed', CaeElapsed);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeCount, CaeElapsed };
export type { CaeEventMap } from '../core/events.js';
