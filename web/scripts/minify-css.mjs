// A Vite plugin for the built bundles (the monitor's `app.js`, ui's `./bundle`):
// the text of each Lit `css` template in the packages' sources loses its
// comments and its runs of whitespace. The rules stay the same; the minifier
// leaves template text alone, so this is what keeps the indentation out.

/**
 * CSS text without comments, with each run of whitespace one space, and none around `{`, `}` and `;`.
 * Quoted strings (`content: '  '`, `"a  b"`) are kept exactly as written; comments go first,
 * so a quote inside a comment does not start a string.
 */
export function minifyCssText(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split(/('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")/)
    .map((part, i) =>
      i % 2
        ? part
        : part
            .replace(/\s+/g, ' ')
            .replace(/ ?([{};]) ?/g, '$1'),
    )
    .join('');
}

/** `code` with the literal text of every css`...` template minified; the `${...}` parts are kept as they are. */
export function minifyCssTemplates(code) {
  const re = /\bcss`/g;
  let out = '';
  let last = 0;
  let m;
  while ((m = re.exec(code))) {
    let i = m.index + m[0].length;
    out += code.slice(last, i);
    let from = i;
    while (i < code.length) {
      const c = code[i];
      if (c === '\\') {
        i += 2;
        continue;
      }
      if (c === '`') {
        out += minifyCssText(code.slice(from, i));
        break;
      }
      if (c === '$' && code[i + 1] === '{') {
        out += minifyCssText(code.slice(from, i));
        let depth = 1;
        let j = i + 2;
        while (j < code.length && depth) {
          if (code[j] === '{') depth++;
          else if (code[j] === '}') depth--;
          j++;
        }
        out += code.slice(i, j);
        i = from = j;
        continue;
      }
      i++;
    }
    last = i;
    re.lastIndex = i + 1;
  }
  return out + code.slice(last);
}

/** @returns {import('vite').Plugin} */
export function minifyCss() {
  return {
    name: 'contraagent-minify-css',
    enforce: 'pre',
    transform(code, id) {
      if (!/\/packages\/[^/]+\/src\/.*\.ts$/.test(id) || !code.includes('css`')) return null;
      return { code: minifyCssTemplates(code), map: null };
    },
  };
}
