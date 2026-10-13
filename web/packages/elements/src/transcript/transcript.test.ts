// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeTranscript } from './transcript.js';
import type { TranscriptSection } from './types.js';

defineElement('cae-transcript', CaeTranscript);

const section = (id: string, items: TranscriptSection['items'] = [], more: Partial<TranscriptSection> = {}): TranscriptSection => ({
  id,
  title: `Session ${id}`,
  items,
  ...more,
});

/** Lets the element update, run what it scheduled after the update, and update again. */
const settle = async (el: CaeTranscript) => {
  await el.updateComplete;
  await frame();
  await el.updateComplete;
};

const frame = () => new Promise((done) => requestAnimationFrame(() => done(null)));

async function mount(props: Partial<CaeTranscript>) {
  const el = document.createElement('cae-transcript');
  Object.assign(el, props);
  const events: string[] = [];
  for (const name of ['cae-section-change', 'cae-section-shown', 'cae-load-earlier'] as const)
    el.addEventListener(name, (e) => events.push(`${name} ${JSON.stringify(e.detail)}`));
  document.body.append(el);
  await el.updateComplete;
  await frame();
  const root = el.shadowRoot!;
  return { el, root, events };
}

/** Puts the scroller of `el` at `top`, with a fixed height: happy-dom lays nothing out. */
function scrollTo(root: ShadowRoot, top: number, height = 1000) {
  const sc = root.querySelector<HTMLElement>('.scroller')!;
  Object.defineProperty(sc, 'scrollHeight', { configurable: true, value: height });
  Object.defineProperty(sc, 'clientHeight', { configurable: true, value: 200 });
  sc.scrollTop = top;
  sc.dispatchEvent(new Event('scroll'));
}

describe('cae-transcript', () => {
  it('shows the latest section, its items, and a picker above two sections', async () => {
    const { el, root, events } = await mount({
      sections: [
        section('a', [{ type: 'message', id: 'm1', text: 'first' }], { verdict: { tone: 'failed', text: 'failed', tip: 'it broke' } }),
        section('b', [
          { type: 'prompt', id: 'p', text: 'do it' },
          { type: 'message', id: 'm2', text: 'second' },
          { type: 'notice', id: 'n', text: 'log line' },
          { type: 'tool', id: 't', name: 'Bash', icon: 'bash', summary: 'ls', output: 'a b', status: 'ok' },
        ], { facts: ['model-x'], footer: { tone: 'attention', title: 'Checks failed', list: ['x: wrong'] } }),
      ],
    });
    const tabs = [...root.querySelectorAll<HTMLButtonElement>('.stab')];
    expect(tabs.map((t) => t.textContent?.replace(/\s+/g, ' ').trim())).toEqual(['✕failedSession a', 'Session b model-x']);
    expect(tabs[1]?.getAttribute('aria-pressed')).toBe('true');
    expect(tabs[0]?.title).toBe('it broke');
    expect([...root.querySelectorAll('.inv-body > *')].map((n) => n.className.trim().split(' ')[0])).toEqual(['msg', 'msg', 'sysline', 'toolcard', 'verdict']);
    expect(root.querySelector('.verdict li')?.textContent).toBe('x: wrong');
    expect(events).toContain('cae-section-shown {"index":1}');

    tabs[0]!.click();
    expect(events).toContain('cae-section-change {"index":0}');
    el.shown = 0;
    await el.updateComplete;
    expect(root.querySelector('.msg .tx')?.textContent).toBe('first');
    tabs[1]!.click();
    expect(events).toContain('cae-section-change {"index":null}');
    el.remove();
  });

  it('opens a tool card from its header, and a web search lists its pages', async () => {
    const { el, root } = await mount({
      sections: [
        section('a', [
          {
            type: 'tool',
            id: 'w',
            name: 'web_search',
            icon: 'search',
            summary: 'lit',
            query: 'lit elements',
            output: 'raw',
            status: 'ok',
            links: [{ title: 'Lit', url: 'https://lit.dev/' }],
          },
        ]),
      ],
    });
    const card = root.querySelector<HTMLElement>('.toolcard')!;
    expect(card.dataset['tool']).toBe('web-search');
    expect(card.querySelector('.ti')?.textContent).toBe('1 result');
    const head = card.querySelector<HTMLElement>('.th')!;
    expect(head.getAttribute('aria-expanded')).toBe('false');
    head.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await el.updateComplete;
    expect(head.getAttribute('aria-expanded')).toBe('true');
    expect(root.querySelector('.wq b')?.textContent).toBe('lit elements');
    expect(root.querySelector<HTMLAnchorElement>('.links a')?.href).toBe('https://lit.dev/');
    expect(root.querySelector('.host')?.textContent).toBe('lit.dev');
    el.remove();
  });

  it('counts what arrives below while the reader is scrolled up, and keeps the section being read', async () => {
    const one = section('a', [{ type: 'message', id: 'm1', text: 'x' }]);
    const { el, root, events } = await mount({ sections: [one], count: 1 });
    scrollTo(root, 0); // scrolled up: no longer following
    el.sections = [one];
    el.count = 4;
    await settle(el);
    expect(root.querySelector('.newpill')?.textContent?.trim()).toBe('Show 3 new events');

    el.sections = [one, section('b')];
    el.count = 5;
    await settle(el);
    expect(el.shownIndex).toBe(0); // pinned to the one being read
    expect(root.querySelector('.newpill')?.textContent?.trim()).toBe('Show 4 new events in the latest session');
    root.querySelector<HTMLButtonElement>('.newpill')!.click();
    await el.updateComplete;
    expect(el.shownIndex).toBe(1);
    expect(root.querySelector('.newpill')).toBeNull();
    expect(events.filter((e) => e.startsWith('cae-section-shown'))).toEqual(['cae-section-shown {"index":0}', 'cae-section-shown {"index":1}']);
    el.remove();
  });

  it('asks for earlier content', async () => {
    const { el, root, events } = await mount({ sections: [section('a')], earlier: 1 });
    const back = root.querySelector<HTMLButtonElement>('.back')!;
    expect(back.textContent?.trim()).toBe('Show 1 earlier line');
    back.click();
    expect(events).toContain('cae-load-earlier {}');
    el.remove();
  });

  it('restores the position from its memory once the content arrives, and keeps open cards there', async () => {
    const open = new Set(['t']);
    const saved: unknown[] = [];
    const memory = {
      isOpen: (id: string) => open.has(id),
      setOpen: (id: string, on: boolean) => void (on ? open.add(id) : open.delete(id)),
      scroll: () => ({ stick: false, top: 0 }),
      setScroll: (at: unknown) => void saved.push(at),
    };
    const card = { type: 'tool' as const, id: 't', name: 'Read', icon: 'read', summary: 'a.txt', output: null, status: 'running' as const };
    const { el, root } = await mount({ sections: [section('a', [card])], loading: true, memory, live: true });
    expect(root.querySelector('.tb')).not.toBeNull(); // open from memory
    expect(root.querySelector('.st-run')).not.toBeNull();
    el.loading = false;
    await el.updateComplete;
    await new Promise((done) => setTimeout(done, 0));
    scrollTo(root, 10);
    expect(saved).toEqual([{ stick: false, top: 10 }]);
    root.querySelector<HTMLElement>('.th')!.click();
    expect(open.has('t')).toBe(false);
    el.live = false;
    await el.updateComplete;
    expect(root.querySelector('.st-int')?.textContent?.trim()).toBe('◌ interrupted');
    el.remove();
  });
});
