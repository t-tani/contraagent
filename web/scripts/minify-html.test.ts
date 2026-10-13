import { describe, expect, it } from 'vitest';
import { minifyHtmlParts, minifyHtmlTemplates } from './minify-html.mjs';

describe('minifyHtmlParts', () => {
  it('turns whitespace with a line break in text into one line break', () => {
    expect(minifyHtmlParts(['<ul>\n    <li>a</li>\n    <li>b</li>\n  </ul>\n']).parts).toEqual(['<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n']);
  });

  it('keeps whitespace without a line break', () => {
    expect(minifyHtmlParts(['<b>a</b>  <i>b</i> c']).parts).toEqual(['<b>a</b>  <i>b</i> c']);
  });

  it("turns whitespace with a line break between a tag's attributes into one space", () => {
    expect(minifyHtmlParts(['<div\n      class="a"\n      id="b"\n    >x</div>']).parts).toEqual(['<div class="a" id="b" >x</div>']);
  });

  it('keeps quoted attribute values as written', () => {
    expect(minifyHtmlParts(['<p title="a\n   b" data-x=\'c\n   d\'>\n  t</p>']).parts).toEqual(['<p title="a\n   b" data-x=\'c\n   d\'>\nt</p>']);
  });

  it('keeps the text inside pre, textarea, code, script and style, and after them minifies again', () => {
    for (const tag of ['pre', 'textarea', 'code', 'script', 'style']) {
      const inner = `<${tag} class="x">\n    a\n      b\n</${tag}>`;
      expect(minifyHtmlParts([`<div>\n  ${inner}\n  </div>`]).parts).toEqual([`<div>\n${inner}\n</div>`]);
    }
  });

  it('follows the state across expressions', () => {
    const r = minifyHtmlParts(['<pre class=', '>\n  ', '\n  </pre>\n  <p title="', '\n  x">\n  ', '</p>']);
    expect(r.parts).toEqual(['<pre class=', '>\n  ', '\n  </pre>\n<p title="', '\n  x">\n', '</p>']);
    expect(r.keep).toEqual([0, 1, 0, 0]);
  });

  it('keeps everything inside a template written inside a kept element', () => {
    expect(minifyHtmlParts(['<i>\n  a</i>'], 1).parts).toEqual(['<i>\n  a</i>']);
  });

  it('keeps comments as written', () => {
    expect(minifyHtmlParts(['<!-- a\n   b -->\n  <i></i>']).parts).toEqual(['<!-- a\n   b -->\n<i></i>']);
  });
});

describe('minifyHtmlTemplates', () => {
  it('minifies html and svg templates, nested ones too, and nothing else', () => {
    const code = [
      'const a = html`<div>\n    ${items.map((i) => html`<li>\n      ${i}</li>`)}\n  </div>`;',
      'const b = svg`<g>\n    <text>t</text></g>`;',
      'const c = css`.a {\n    color: red; }`;',
      'const d = `<div>\n    plain</div>`;',
      "const e = html`<pre>${lines.map((l) => html`<span>\n  ${l}</span>`)}</pre>`;",
    ].join('\n');
    expect(minifyHtmlTemplates(code)).toBe(
      [
        'const a = html`<div>\n${items.map((i) => html`<li>\n${i}</li>`)}\n</div>`;',
        'const b = svg`<g>\n<text>t</text></g>`;',
        'const c = css`.a {\n    color: red; }`;',
        'const d = `<div>\n    plain</div>`;',
        "const e = html`<pre>${lines.map((l) => html`<span>\n  ${l}</span>`)}</pre>`;",
      ].join('\n'),
    );
  });

  it('reads TypeScript', () => {
    const code = 'const x = (n: number): TemplateResult => html`<b>\n  ${n as number}</b>`;';
    expect(minifyHtmlTemplates(code)).toBe('const x = (n: number): TemplateResult => html`<b>\n${n as number}</b>`;');
  });
});
