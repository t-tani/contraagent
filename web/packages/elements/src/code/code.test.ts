// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeCode, isMarked, shownText } from './code.js';
import { highlight, languageOf, tokenLines, tokenize, LANGUAGES } from './highlight.js';

defineElement('cae-code', CaeCode);

// A test may put its own clipboard on navigator; the next one sees the page's again.
const clipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
afterEach(() => {
  if (clipboard) Object.defineProperty(navigator, 'clipboard', clipboard);
  else delete (navigator as { clipboard?: unknown }).clipboard;
});

const types = (code: string, lang: string) => tokenize(code, lang).filter((t) => t.type).map((t) => `${t.type}:${t.text}`);

describe('the highlighter', () => {
  it('reads a language by its name, another name of it, a file name or an extension', () => {
    expect(languageOf('python')).toBe('python');
    expect(languageOf('PY')).toBe('python');
    expect(languageOf('src/app/main.rs')).toBe('rust');
    expect(languageOf('page.tsx')).toBe('typescript');
    expect(languageOf('yml')).toBe('yaml');
    expect(languageOf('cobol')).toBe('');
    expect(LANGUAGES.every((l) => languageOf(l) === l)).toBe(true);
  });

  it('names the tokens of each language', () => {
    expect(types('def run(x):  # go\n    return None', 'python')).toEqual(['keyword:def', 'function:run', 'comment:# go', 'keyword:return', 'constant:None']);
    expect(types('{"a": [1, true, "s"]}', 'json')).toEqual(['key:"a"', 'number:1', 'constant:true', 'string:"s"']);
    expect(types('const f = function g() { return `t${1}`; } // c', 'js')).toEqual([
      'keyword:const',
      'keyword:function',
      'function:g',
      'keyword:return',
      'string:`t${1}`',
      'comment:// c',
    ]);
    expect(types('#include <stdio.h>\nint main(void) { return 0; }', 'c')).toEqual(['meta:#include', 'keyword:int', 'keyword:void', 'keyword:return', 'number:0']);
    expect(types("fn f<'a>(s: &'a str) { println!(\"x\"); }", 'rust')).toEqual([
      'keyword:fn',
      'function:f',
      "type:'a",
      "type:'a",
      'builtin:str',
      'builtin:println!',
      'string:"x"',
    ]);
    expect(types('echo "$HOME" # done', 'sh')).toEqual(['builtin:echo', 'string:"$HOME"', 'comment:# done']);
    expect(types('[tool]\nname = "x"', 'toml')).toEqual(['class:[tool]', 'key:name', 'string:"x"']);
    expect(types('SELECT id FROM t WHERE n = 1', 'sql')).toEqual(['keyword:SELECT', 'keyword:FROM', 'keyword:WHERE', 'number:1']);
    expect(types('<a href="x">don\'t</a>', 'html')).toEqual(['tag:<a', 'attribute:href', 'string:"x"', 'tag:>', 'tag:</a>']); // tokens of one type side by side are one
    expect(types('@@ -1 +1 @@\n-old\n+new', 'diff')).toEqual(['meta:@@ -1 +1 @@', 'deleted:-old', 'inserted:+new']);
  });

  it('escapes every token, so no text injects markup', () => {
    expect(highlight('x = "<b>"', 'python')).toBe('x = <span class="hl-s">&quot;&lt;b&gt;&quot;</span>');
    expect(highlight('<script>', 'none')).toBe('&lt;script&gt;');
  });

  it('splits a token across lines into one piece per line', () => {
    const lines = tokenLines(tokenize('a = """one\ntwo"""\nb', 'python'));
    expect(lines.map((l) => l.map((t) => t.text).join(''))).toEqual(['a = """one', 'two"""', 'b']);
    expect(lines[1]![0]!.type).toBe('doc');
  });
});

describe('a text shown as code', () => {
  it('shows the first lines of a long text and counts all of them', () => {
    expect(shownText('a\nb\nc\n', 2, 100)).toEqual({ shown: 'a\nb', lines: 2, total: 3, cut: true });
    expect(shownText('a\nb\nc\n', 5, 100)).toEqual({ shown: 'a\nb\nc', lines: 3, total: 3, cut: false });
    expect(shownText('aaaa\nbbbb', 5, 6)).toEqual({ shown: 'aaaa', lines: 1, total: 2, cut: true }); // cut at the end of a line
    expect(shownText('aaaaaaaa', 5, 3)).toEqual({ shown: 'aaa', lines: 1, total: 1, cut: true }); // a first line longer than the limit
    expect(shownText('', 5, 3)).toEqual({ shown: '', lines: 0, total: 0, cut: false });
  });

  it('marks a line and the lines of a range', () => {
    expect([1, 2, 3, 4, 5].filter((n) => isMarked([1, [3, 4]], n))).toEqual([1, 3, 4]);
  });

  it('numbers its lines from start, marks the highlighted ones, says how many it left out, and copies the whole text', async () => {
    const el = document.createElement('cae-code');
    Object.assign(el, { code: 'x = 1\ny = 2\nz = 3\n', language: 'py', start: 10, highlight: [11], maxLines: 2, path: 'a.py', strings: { cut: (s: number, t: number) => `${s}/${t}` } });
    let copied = '';
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: (t: string) => Promise.resolve(void (copied = t)) }, configurable: true });
    document.body.append(el);
    await el.updateComplete;
    const root = el.shadowRoot!;
    const lines = [...root.querySelectorAll<HTMLElement>('.ln')];
    expect(lines.map((l) => [l.dataset['n'], l.hasAttribute('data-mark'), l.textContent])).toEqual([
      ['10', false, 'x = 1'],
      ['11', true, 'y = 2'],
    ]);
    expect(root.querySelector('[part=cut]')?.textContent).toBe('2/3');
    expect(root.querySelector('[part=code]')?.getAttribute('aria-label')).toBe('a.py');
    const [wrap, copy] = root.querySelectorAll<HTMLButtonElement>('.tools button');
    wrap!.click();
    await el.updateComplete;
    expect(root.querySelector('.scroll')!.classList.contains('wrap')).toBe(true);
    expect(wrap!.getAttribute('aria-pressed')).toBe('true');
    copy!.click();
    await vi.waitFor(() => expect(copied).toBe('x = 1\ny = 2\nz = 3\n'));
    await vi.waitFor(() => expect(copy!.textContent).toBe('Copied'));
    el.remove();
  });
});
