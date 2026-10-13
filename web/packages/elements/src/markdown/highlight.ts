// Syntax highlighting: a small tokenizer for what plugins and contracts contain
// (Python, JSON), no library. Returns escaped HTML: every token is escaped
// before it is wrapped, so no input can inject markup.
import { esc } from '../core/format.js';

const PY_KW = new Set(
  'and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield'.split(
    ' ',
  ),
);
const PY_CONST = new Set(['None', 'True', 'False', 'self', 'cls']);
const PY_BUILTIN = new Set(
  'str int float bool list dict set tuple bytes object type len range print isinstance super Optional Literal Any Union Path'.split(' '),
);
const PY_TOKEN = new RegExp(
  [
    '(#[^\\n]*)', // 1 comment
    '((?:[rRbBfFuU]{0,2})(?:"""[\\s\\S]*?"""|\'\'\'[\\s\\S]*?\'\'\'))', // 2 triple-quoted string (docstrings)
    '((?:[rRbBfFuU]{0,2})(?:"(?:[^"\\\\\\n]|\\\\.)*"|\'(?:[^\'\\\\\\n]|\\\\.)*\'))', // 3 string
    '(@[A-Za-z_][\\w.]*)', // 4 decorator
    '(\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)', // 5 number
    '([A-Za-z_]\\w*)', // 6 name
  ].join('|'),
  'g',
);

export function hlPython(src: string): string {
  let out = '';
  let last = 0;
  let prevWord = '';
  PY_TOKEN.lastIndex = 0;
  for (let m = PY_TOKEN.exec(src); m; m = PY_TOKEN.exec(src)) {
    out += esc(src.slice(last, m.index));
    last = PY_TOKEN.lastIndex;
    const [tok, com, tri, str, dec, num, name] = m;
    if (com) out += `<span class="hl-c">${esc(tok)}</span>`;
    else if (tri) out += `<span class="hl-s hl-doc">${esc(tok)}</span>`;
    else if (str) out += `<span class="hl-s">${esc(tok)}</span>`;
    else if (dec) out += `<span class="hl-d">${esc(tok)}</span>`;
    else if (num) out += `<span class="hl-n">${esc(tok)}</span>`;
    else if (name) {
      const cls = PY_KW.has(name)
        ? 'hl-k'
        : PY_CONST.has(name)
          ? 'hl-k hl-const'
          : prevWord === 'class'
            ? 'hl-cls'
            : prevWord === 'def'
              ? 'hl-f'
              : PY_BUILTIN.has(name)
                ? 'hl-b'
                : /^[A-Z]\w*$/.test(name) && name.length > 1 && /[a-z]/.test(name)
                  ? 'hl-t'
                  : '';
      out += cls ? `<span class="${cls}">${esc(name)}</span>` : esc(name);
      prevWord = name;
      continue;
    }
    if (!/^\s*$/.test(tok)) prevWord = '';
  }
  return out + esc(src.slice(last));
}

export function hlJson(src: string): string {
  const re = /("(?:[^"\\\n]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)/g;
  let out = '';
  let last = 0;
  for (let m = re.exec(src); m; m = re.exec(src)) {
    out += esc(src.slice(last, m.index));
    last = re.lastIndex;
    const [, str, colon, kw, num] = m;
    out += str
      ? colon
        ? `<span class="hl-key">${esc(str)}</span>${esc(colon)}`
        : `<span class="hl-s">${esc(str)}</span>`
      : kw
        ? `<span class="hl-k hl-const">${kw}</span>`
        : `<span class="hl-n">${num ?? ''}</span>`;
  }
  return out + esc(src.slice(last));
}

const LANG_OF: Record<string, 'python' | 'json'> = { py: 'python', python: 'python', json: 'json', jsonc: 'json' };

function langOf(hint: string | null | undefined): 'python' | 'json' | '' {
  const h = String(hint || '').toLowerCase();
  return LANG_OF[h.replace(/^.*\./, '')] || LANG_OF[h] || '';
}

/** Highlighted, escaped HTML. `hint` is a fence language ("python") or a file name ("schema.py"); anything unknown is plain. */
export function highlight(code: string, hint?: string | null): string {
  const lang = langOf(hint);
  return lang === 'python' ? hlPython(code) : lang === 'json' ? hlJson(code) : esc(code);
}
