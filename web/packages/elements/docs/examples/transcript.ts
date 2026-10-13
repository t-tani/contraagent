// A conversation with a support bot in two sessions: the first ended with a
// failed lookup, the second answered. The host holds the sections and decides
// what a reader's pick means: here the picked session is simply shown.
import '@contraagent/elements/transcript/define';
import { md } from '@contraagent/elements/markdown';
import type { TranscriptSection } from '@contraagent/elements/transcript';

const sections: TranscriptSection[] = [
  {
    id: 's1',
    title: 'Session 1',
    verdict: { tone: 'failed', text: 'failed', tip: 'The order service did not answer' },
    tags: [
      { label: 'bot', value: 'helpdesk' },
      { label: 'model', value: 'small-2', look: 'mono' },
    ],
    items: [
      { type: 'prompt', id: 'p1', text: 'Where is order 1042?' },
      { type: 'reasoning', id: 'r1', text: 'Look the order up first, then answer with its **status**.' },
      { type: 'tool', id: 't1', name: 'orders.get', icon: 'read', summary: 'order 1042', output: 'timeout after 30s', status: 'error' },
    ],
    footer: { tone: 'failed', title: 'The order service did not answer' },
  },
  {
    id: 's2',
    title: 'Session 2',
    facts: ['small-2'],
    verdict: { tone: 'done', text: 'answered' },
    items: [
      { type: 'event', id: 'e1', icon: '↻', title: 'Request sent again', text: 'after a timeout' },
      {
        type: 'tool',
        id: 't2',
        name: 'web_search',
        icon: 'search',
        summary: 'carrier tracking 1042',
        query: 'carrier tracking 1042',
        links: [
          { title: 'Track a parcel', url: 'https://example.com/track' },
          { title: 'Delivery times', url: 'https://example.org/delivery' },
        ],
        output: 'Track a parcel https://example.com/track\nDelivery times https://example.org/delivery',
        status: 'ok',
      },
      { type: 'notice', id: 'n1', text: 'cache hit: orders/1042' },
      { type: 'message', id: 'm1', text: 'Order **1042** left the warehouse on Monday and arrives on *Thursday*.' },
    ],
  },
];

export function mount(host: HTMLElement): void {
  const t = document.createElement('cae-transcript');
  t.sections = sections;
  t.markdown = md;
  t.strings = { sections: 'Sessions', sectionsTip: 'One session per conversation with the bot' };
  t.style.height = '420px';
  t.addEventListener('cae-section-change', (e) => (t.shown = e.detail.index));
  host.replaceChildren(t);
}
