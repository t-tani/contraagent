// A Vite plugin for the built bundles (the monitor's `app.js`, ui's `./bundle`): in the text of
// each Lit `html` and `svg` template of the packages' sources, the indentation after a line break
// goes. The minifier leaves template text alone, so this is what keeps the indentation out.
//
// Where whitespace is shown as written, nothing changes: inside <pre>, <textarea>, <code>,
// <script> and <style>, in a template written inside one of them, and in an attribute's quoted
// value. Elsewhere a line break and the spaces around it render as one space (white-space normal
// or nowrap) or as one line break (pre-line), so a run of whitespace with a line break in it
// becomes one line break in text and one space between a tag's attributes.
import ts from 'typescript';

/** The elements whose text keeps its whitespace. */
const KEEP = new Set(['pre', 'textarea', 'code', 'script', 'style']);

/**
 * One template's literal parts, minified in order; `keep` is the depth of KEEP elements open
 * around the template. Returns the new parts, and the depth of KEEP elements open before each
 * expression (index i: the expression after part i).
 */
export function minifyHtmlParts(parts, keep = 0) {
  /** @type {'text' | 'tag' | 'dq' | 'sq' | 'comment'} */
  let state = 'text';
  const open = []; // KEEP elements opened in this template
  let tagName = null; // the name of the tag being read, when it opens a KEEP element
  const before = [];
  const out = parts.map((raw, p) => {
    let o = '';
    let i = 0;
    while (i < raw.length) {
      const c = raw[i];
      if (state === 'comment') {
        if (raw.startsWith('-->', i)) {
          o += '-->';
          i += 3;
          state = 'text';
        } else o += raw[i++];
        continue;
      }
      if (state === 'dq' || state === 'sq') {
        if (c === '\\') {
          o += raw.slice(i, i + 2);
          i += 2;
          continue;
        }
        if (c === (state === 'dq' ? '"' : "'")) state = 'tag';
        o += raw[i++];
        continue;
      }
      if (state === 'tag') {
        if (c === '"' || c === "'") {
          state = c === '"' ? 'dq' : 'sq';
          o += raw[i++];
          continue;
        }
        if (c === '>') {
          if (tagName && raw[i - 1] !== '/') open.push(tagName);
          tagName = null;
          state = 'text';
          o += raw[i++];
          continue;
        }
        const ws = /^\s+/.exec(raw.slice(i));
        if (ws) {
          o += ws[0].includes('\n') ? ' ' : ws[0];
          i += ws[0].length;
          continue;
        }
        o += raw[i++];
        continue;
      }
      // text
      if (raw.startsWith('<!--', i)) {
        o += '<!--';
        i += 4;
        state = 'comment';
        continue;
      }
      if (c === '<') {
        const m = /^<(\/?)([a-zA-Z][\w-]*)/.exec(raw.slice(i));
        if (m) {
          const name = m[2].toLowerCase();
          if (m[1]) {
            if (KEEP.has(name) && open.at(-1) === name) open.pop();
          } else if (KEEP.has(name)) tagName = name;
          state = 'tag';
          o += m[0];
          i += m[0].length;
          continue;
        }
      }
      const ws = /^\s+/.exec(raw.slice(i));
      if (ws) {
        o += ws[0].includes('\n') && keep + open.length === 0 ? '\n' : ws[0];
        i += ws[0].length;
        continue;
      }
      o += raw[i++];
    }
    if (p < parts.length - 1) before.push(keep + open.length);
    return o;
  });
  return { parts: out, keep: before };
}

/** `code` (TypeScript or JavaScript) with the text of every `html` and `svg` tagged template minified. */
export function minifyHtmlTemplates(code, fileName = 'x.ts') {
  const sf = ts.createSourceFile(fileName, code, ts.ScriptTarget.Latest, true);
  /** @type {[number, number, string][]} */
  const edits = [];
  const visit = (node, keep) => {
    if (ts.isTaggedTemplateExpression(node) && ts.isIdentifier(node.tag) && (node.tag.text === 'html' || node.tag.text === 'svg')) {
      const t = node.template;
      // [start, end) of each literal part's raw text, without its `, ${ and }
      const ranges = ts.isNoSubstitutionTemplateLiteral(t)
        ? [[t.getStart(sf) + 1, t.end - 1]]
        : [
            [t.head.getStart(sf) + 1, t.head.end - 2],
            ...t.templateSpans.map((s) => [s.literal.getStart(sf) + 1, s.literal.end - (ts.isTemplateTail(s.literal) ? 1 : 2)]),
          ];
      const { parts, keep: inner } = minifyHtmlParts(
        ranges.map(([a, b]) => code.slice(a, b)),
        keep,
      );
      ranges.forEach(([a, b], i) => {
        if (parts[i] !== code.slice(a, b)) edits.push([a, b, parts[i]]);
      });
      if (!ts.isNoSubstitutionTemplateLiteral(t)) t.templateSpans.forEach((s, i) => visit(s.expression, inner[i]));
      return;
    }
    ts.forEachChild(node, (n) => visit(n, keep));
  };
  visit(sf, 0);
  let out = code;
  for (const [a, b, s] of edits.sort((x, y) => y[0] - x[0])) out = out.slice(0, a) + s + out.slice(b);
  return out;
}

/** @returns {import('vite').Plugin} */
export function minifyHtml() {
  return {
    name: 'contraagent-minify-html',
    enforce: 'pre',
    transform(code, id) {
      if (!/\/packages\/[^/]+\/src\/.*\.ts$/.test(id) || !/\b(html|svg)`/.test(code)) return null;
      return { code: minifyHtmlTemplates(code, id), map: null };
    },
  };
}
