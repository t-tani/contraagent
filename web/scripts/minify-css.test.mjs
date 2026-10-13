import { describe, expect, it } from 'vitest';
import { minifyCssTemplates, minifyCssText } from './minify-css.mjs';

describe('minifyCssText', () => {
  it('drops comments and runs of whitespace', () => {
    expect(minifyCssText('/* a comment, don\'t */\n.b  {\n  color: red ;\n}\n')).toBe(' .b{color: red;}');
  });

  it('keeps quoted strings as written', () => {
    expect(minifyCssText(".a::before { content: '  x ; y  '; }")).toBe(".a::before{content: '  x ; y  ';}");
    expect(minifyCssText('.g { grid-template-areas: "a  b" "c  d"; }')).toBe('.g{grid-template-areas: "a  b" "c  d";}');
  });
});

describe('minifyCssTemplates', () => {
  it('minifies the css template text and keeps the ${…} parts', () => {
    const code = 'const s = css`\n  .a {\n    color: ${tone};\n  }\n`;';
    expect(minifyCssTemplates(code)).toBe('const s = css` .a{color: ${tone};}`;');
  });
});
