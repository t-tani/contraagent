// A tool call as a card: its name, summary and status on one line; open, its
// command and output (long ones folded), or a web search's query and the pages
// it returned, or a page's URL.
import { html, nothing, type TemplateResult } from 'lit';
import type { ToolCard, TranscriptStrings } from './types.js';

/** Tool output longer than this is folded. */
const FOLD_AT = 1200;
/** A tool card shows at most this much of a command or an output. */
const SHOW_MAX = 4000;

/** What a card needs of the element that draws it. */
export interface CardHost {
  s: TranscriptStrings;
  live: boolean;
  /** The card scrolled to by `reveal`. */
  revealed: string;
  isOpen(id: string): boolean;
  toggle(id: string): void;
  /** The folded code blocks that are unfolded. */
  folds: Set<string>;
  requestUpdate(): void;
}

/** The host of a URL, for the line under a result; '' when it does not parse. */
function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return '';
  }
}

function codeBlock(h: CardHost, text: string, id: string): TemplateResult {
  const pre = html`<pre><code>${text.slice(0, SHOW_MAX)}</code></pre>`;
  if (text.length <= FOLD_AT) return pre;
  const open = h.folds.has(id);
  return html`<div>
    <div class="fold ${open ? 'open' : ''}">${pre}</div>
    <button type="button" class="foldbtn" @click=${() => {
      if (open) h.folds.delete(id);
      else h.folds.add(id);
      h.requestUpdate();
    }}>${open ? h.s.showLess : h.s.showAll(text.length)}</button>
  </div>`;
}

/** The open card's body: a web search's query and its links, or a page's URL, or the command; then the output. */
function cardBody(h: CardHost, c: ToolCard) {
  const out = c.output;
  const links = c.links ?? [];
  const subject = c.query || c.page;
  if (!subject) {
    return out === null
      ? codeBlock(h, c.body ?? '', `${c.id}:cmd`)
      : html`${c.body ? codeBlock(h, c.body, `${c.id}:cmd`) : nothing}${codeBlock(h, out, `${c.id}:out`)}`;
  }
  const url = !c.query && /^https?:\/\//.test(subject);
  return html`<div class="wq">
      <span class="wl">${c.query ? h.s.query : h.s.page}</span>${url
        ? html`<a class="plink" href=${subject} target="_blank" rel="noopener noreferrer">${subject}</a>`
        : html`<b>${subject}</b>`}
    </div>
    ${links.length
      ? html`<ol class="links">
          ${links.map(
            (r) => html`<li><a href=${r.url} target="_blank" rel="noopener noreferrer">${r.title}</a><span class="host">${hostOf(r.url)}</span></li>`,
          )}
        </ol>`
      : nothing}
    ${out === null
      ? nothing
      : links.length
        ? html`<details class="rawfold"><summary>${h.s.fullText}</summary>${codeBlock(h, out, `${c.id}:out`)}</details>`
        : codeBlock(h, out, `${c.id}:out`)}`;
}

export function toolCard(h: CardHost, c: ToolCard): TemplateResult {
  const { s } = h;
  const open = h.isOpen(c.id);
  const n = c.links?.length ?? 0;
  const status =
    c.status === 'ok'
      ? html`<span class="st-ok"><span aria-hidden="true">✓</span> ${s.done}</span>`
      : c.status === 'error'
        ? html`<span class="st-err"><span aria-hidden="true">✕</span> ${s.failed}</span>`
        : h.live
          ? html`<span class="st-run"><i class="pdot"></i>${s.running}</span>`
          : html`<span class="st-int" title=${s.interruptedTip}><span aria-hidden="true">◌</span> ${s.interrupted}</span>`;
  const cls = c.status === 'running' ? 'run' : c.status === 'error' ? 'err' : 'ok';
  return html`<div class="toolcard ${cls} ${h.revealed === c.id ? 'revealed' : ''}" part="tool" data-tool=${c.query ? 'web-search' : c.page ? 'web-fetch' : c.icon} data-card=${c.id}>
    <div class="th" role="button" tabindex="0" aria-expanded=${open ? 'true' : 'false'} @click=${() => h.toggle(c.id)} @keydown=${(e: KeyboardEvent) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      (e.currentTarget as HTMLElement).click();
    }}>
      <span class="tn">${c.name || s.tool}</span><span class="tp">${c.summary}</span><span class="ti ${n ? '' : 'intent'}"
        >${n ? s.results(n) : c.intent}</span
      >${status}
    </div>
    ${open ? html`<div class="tb" part="tool-body">${cardBody(h, c)}</div>` : nothing}
  </div>`;
}
