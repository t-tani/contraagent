// Registers <cae-markdown>.
import { defineElement } from '../core/define.js';
import { CaeMarkdown } from '../markdown/cae-markdown.js';

defineElement('cae-markdown', CaeMarkdown);

// The classes, and the events' types (`HTMLElementEventMap`), for a page that imports only this entry.
export { CaeMarkdown };
export type { CaeEventMap } from '../core/events.js';
