// A line of Python as HTML, its tokens in spans the landing page colours with
// the themes' code tokens (--ca-code-*). Built with the site: no highlighter in the page.

const KEYWORDS = new Set([
  'async', 'def', 'await', 'return', 'yield', 'try', 'except', 'while', 'if', 'else', 'elif', 'break', 'for', 'in', 'is', 'not', 'and', 'or',
  'import', 'from', 'class', 'with', 'as', 'raise', 'pass', 'lambda',
]);
const CONSTANTS = new Set(['True', 'False', 'None']);

const escape = (s: string): string => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const span = (cls: string, s: string): string => `<span class="t-${cls}">${escape(s)}</span>`;

const TOKEN = /("""[^]*?"""|"[^"\n]*"|'[^'\n]*'|#.*$|\b\d+(?:\.\d+)?\b|[A-Za-z_][A-Za-z0-9_]*|\s+|.)/g;

/** Lines of Python, each highlighted (brackets carry from one line to the next). */
export function highlight(lines: string[]): string[] {
  let depth = 0;
  return lines.map((line) => {
    const [html, after] = highlightLine(line, depth);
    depth = after;
    return html;
  });
}

function highlightLine(line: string, depth: number): [string, number] {
  const parts = line.match(TOKEN) ?? [];
  let out = '';
  let prev = '';
  parts.forEach((tok, i) => {
    if ('([{'.includes(tok)) depth++;
    if (')]}'.includes(tok)) depth--;
    const next = parts.slice(i + 1).find((p) => p.trim() !== '') ?? '';
    if (/^("|')/.test(tok)) out += span('string', tok);
    else if (tok.startsWith('#')) out += span('comment', tok);
    else if (/^\d/.test(tok)) out += span('number', tok);
    else if (/^[A-Za-z_]/.test(tok)) {
      if (KEYWORDS.has(tok)) out += span('keyword', tok);
      else if (CONSTANTS.has(tok)) out += span('constant', tok);
      else if (prev === 'def') out += span('function', tok);
      else if (next === '(') out += span('function', tok);
      else if (next === '=' && depth > 0) out += span('name', tok);
      else if (/^[A-Z]/.test(tok)) out += span('type', tok);
      else out += escape(tok);
    } else out += escape(tok);
    if (tok.trim() !== '') prev = tok;
  });
  return [out, depth];
}
