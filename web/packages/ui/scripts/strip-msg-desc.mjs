// A Vite plugin for the built bundles (the monitor's `app.js`, ui's `./bundle`): a `msg()` call's
// `desc` is a note for translators. `pnpm i18n` writes it into the XLIFF files; Lit Localize does
// not read it at run time, so a bundle need not carry it. Each `msg(…, { …, desc: … })` of the
// packages' sources keeps its other options (`id`), and loses the options object when `desc` was
// the only one.
import ts from 'typescript';

/** `code` (TypeScript or JavaScript) with the `desc` option of every `msg()` call taken out. */
export function stripMsgDesc(code, fileName = 'x.ts') {
  const sf = ts.createSourceFile(fileName, code, ts.ScriptTarget.Latest, true);
  /** @type {[number, number, string][]} */
  const edits = [];
  const visit = (node) => {
    const opts = ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'msg' ? node.arguments[1] : undefined;
    if (opts && ts.isObjectLiteralExpression(opts)) {
      const isDesc = (p) => ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === 'desc';
      const kept = opts.properties.filter((p) => !isDesc(p));
      if (kept.length < opts.properties.length) {
        edits.push(
          kept.length
            ? [opts.getStart(sf), opts.end, `{ ${kept.map((p) => p.getText(sf)).join(', ')} }`]
            : [node.arguments[0].end, opts.end, ''],
        );
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  let out = code;
  for (const [a, b, s] of edits.sort((x, y) => y[0] - x[0])) out = out.slice(0, a) + s + out.slice(b);
  return out;
}

/** @returns {import('vite').Plugin} */
export function stripMsgDescs() {
  return {
    name: 'contraagent-strip-msg-desc',
    enforce: 'pre',
    transform(code, id) {
      if (!/\/packages\/[^/]+\/src\/.*\.ts$/.test(id) || !/\bdesc\b/.test(code)) return null;
      return { code: stripMsgDesc(code, id), map: null };
    },
  };
}
