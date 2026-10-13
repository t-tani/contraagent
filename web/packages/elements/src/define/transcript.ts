// Registers <cae-transcript>.
import { defineElement } from '../core/define.js';
import { CaeTranscript } from '../transcript/transcript.js';

defineElement('cae-transcript', CaeTranscript);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeTranscript };
export type { CaeEventMap } from '../core/events.js';
