// Markdown: what agents and plugin files actually use. Everything is escaped
// first, so nothing the model or a file wrote can inject markup; links keep
// only http(s) targets. Returns HTML for `unsafeHTML`.
import { esc } from './format.js';
import { highlight } from './highlight.js';

function mdInline(t: string): string {
  return t
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a class="lnk" href="$2" target="_blank" rel="noopener">$1</a>');
}

interface Segment {
  t: 'text' | 'code';
  s: string;
  lang?: string;
}

/** Text and fenced code; an unclosed fence (a live stream) runs to the end. */
function mdSplit(text: string): Segment[] {
  const out: Segment[] = [];
  let pos = 0;
  for (;;) {
    const open = text.indexOf('```', pos);
    if (open < 0) {
      out.push({ t: 'text', s: text.slice(pos) });
      return out;
    }
    out.push({ t: 'text', s: text.slice(pos, open) });
    const nl = text.indexOf('\n', open + 3);
    const lang = text.slice(open + 3, nl < 0 ? text.length : nl).trim();
    const start = nl < 0 ? text.length : nl + 1;
    const close = text.indexOf('```', start);
    if (close < 0) {
      out.push({ t: 'code', s: text.slice(start), lang });
      return out;
    }
    out.push({ t: 'code', s: text.slice(start, close), lang });
    pos = close + 3;
  }
}

const TABLE_ROW = /^\s*\|.*\|\s*$/;

export function md(text: string | null | undefined): string {
  return mdSplit(String(text || ''))
    .map((seg) => {
      if (seg.t === 'code') return `<pre><code class="hl">${highlight(seg.s, seg.lang)}</code></pre>`;
      const lines = esc(seg.s).split('\n');
      const out: string[] = [];
      for (let k = 0; k < lines.length; k++) {
        const line = lines[k] ?? '';
        let m: RegExpMatchArray | null;
        if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
          out.push(`<div class="md-h md-h${Math.min(m[1]!.length, 4)}">${mdInline(m[2]!)}</div>`);
        } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
          out.push('<hr class="md-hr">');
        } else if ((m = line.match(/^\s*&gt;\s?(.*)$/))) {
          out.push(`<div class="md-q">${mdInline(m[1]!)}</div>`);
        } else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
          out.push(`<div class="md-li">${mdInline(m[1]!)}</div>`);
        } else if ((m = line.match(/^\s*(\d+)[.)]\s+(.*)$/))) {
          out.push(`<div class="md-li md-ol"><span class="md-n">${m[1]}.</span>${mdInline(m[2]!)}</div>`);
        } else if (TABLE_ROW.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[k + 1] ?? '')) {
          const cells = (l: string) =>
            l
              .trim()
              .replace(/^\||\|$/g, '')
              .split('|')
              .map((c) => mdInline(c.trim()));
          const head = cells(line);
          k += 2;
          const rows: string[][] = [];
          while (k < lines.length && TABLE_ROW.test(lines[k] ?? '')) rows.push(cells(lines[k++] ?? ''));
          k--;
          out.push(
            `<table class="md-t"><tr>${head.map((c) => `<th>${c}</th>`).join('')}</tr>` +
              rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('') +
              '</table>',
          );
        } else {
          out.push(line.trim() === '' ? '<div class="md-gap"></div>' : `<div class="md-p">${mdInline(line)}</div>`);
        }
      }
      return out.join('');
    })
    .join('');
}

/** A markdown file as a person reads it: its `---` front matter as a small table, then the body. */
export function mdFile(text: string | null | undefined, mark?: (html: string) => string): string {
  const src = String(text || '');
  const m = src.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  let front = '';
  let body = src;
  if (m) {
    body = m[2] ?? '';
    const rows = (m[1] ?? '')
      .split('\n')
      .map((l) => l.match(/^([\w-]+):\s*(.*)$/))
      .filter((x): x is RegExpMatchArray => !!x)
      .map(([, k, v]) => `<tr><td class="jmono">${esc(k)}</td><td>${esc(v)}</td></tr>`)
      .join('');
    front = rows ? `<table class="md-front">${rows}</table>` : '';
  }
  const html = md(body);
  return `<div class="md-doc">${front}${mark ? mark(html) : html}</div>`;
}

/** `$unit` and `{{contract}}` picked out of an instructions template (escaped source). */
export function instructionsHtml(text: string): string {
  return markInstructions(esc(text));
}

/** The same, on already-rendered HTML. */
export const markInstructions = (html: string): string =>
  html
    .replace(/\$\{?([A-Za-z_]\w*)\}?/g, '<span class="pv">$&</span>')
    .replace(/\{\{contract\}\}/g, '<span class="pv pc">{{contract}}</span>');

/** A prompt's leading `TELEMETRY ...` line (which run and task it belongs to), apart from its prose. */
export function splitTelemetry(text: string): { telemetry: string; body: string } {
  const m = text.match(/^(TELEMETRY [^\n]*)\n+([\s\S]*)$/);
  return m ? { telemetry: m[1] ?? '', body: m[2] ?? '' } : { telemetry: '', body: text };
}
