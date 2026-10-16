// Syntax highlighting: a small tokenizer for a fixed set of languages, no library.
// Each language is a few regular expressions and its words; a token is a piece of
// the text and what it is. `highlight` returns escaped HTML: every token is escaped
// before it is wrapped, so no input can inject markup.
import { esc } from '../core/format.js';

/** What a token is; '' for text of no colour. */
export type TokenType =
  | 'comment'
  | 'doc'
  | 'string'
  | 'number'
  | 'keyword'
  | 'constant'
  | 'builtin'
  | 'type'
  | 'function'
  | 'class'
  | 'decorator'
  | 'key'
  | 'tag'
  | 'attribute'
  | 'inserted'
  | 'deleted'
  | 'meta'
  | '';

/** A piece of the text and what it is. */
export interface CodeToken {
  text: string;
  type: TokenType;
}

/** The languages highlighted, by name; `languageOf` reads their other names and file extensions. */
export const LANGUAGES = ['python', 'json', 'javascript', 'typescript', 'c', 'cpp', 'java', 'go', 'rust', 'shell', 'toml', 'yaml', 'sql', 'xml', 'diff'] as const;
export type Language = (typeof LANGUAGES)[number];

interface Grammar {
  /** The patterns, tried in order at each place: a token type and a regular expression with no capturing group. */
  rules: readonly (readonly [TokenType, string])[];
  keywords?: ReadonlySet<string>;
  constants?: ReadonlySet<string>;
  builtins?: ReadonlySet<string>;
  /** The words after which a name is a function's or a type's own name. */
  defines?: Readonly<Record<string, 'function' | 'class'>>;
  /** A capitalized name (`Path`) is a type. */
  types?: boolean;
  /** The words compare in any case (SQL). */
  caseless?: boolean;
  /** A name; none: the words outside the rules have no colour. */
  name?: string | null;
}

const words = (s: string): ReadonlySet<string> => new Set(s.split(' '));

const LINE_C = ['comment', '//[^\\n]*|/\\*[\\s\\S]*?\\*/'] as const;
const DQ = '"(?:[^"\\\\\\n]|\\\\.)*"';
const SQ = "'(?:[^'\\\\\\n]|\\\\.)*'";
const CHAR = "'(?:[^'\\\\\\n]|\\\\.)'";
const NUMBER = ['number', "\\b(?:0[xX][\\da-fA-F_']+|0[bB][01_]+|\\d[\\d_']*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?)[uUlLfFn]*\\b"] as const;
const NAME = '[A-Za-z_$][\\w$]*';

const JS_KW =
  'break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch throw try typeof var void while with yield async await as';
const C_KW =
  'auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while bool';
const C_DEFINES = { struct: 'class', class: 'class', enum: 'class', union: 'class' } as const;

const GRAMMARS: Record<Language, Grammar> = {
  python: {
    rules: [
      ['comment', '#[^\\n]*'],
      ['doc', '(?:[rRbBfFuU]{0,2})(?:"""[\\s\\S]*?"""|\'\'\'[\\s\\S]*?\'\'\')'],
      ['string', `(?:[rRbBfFuU]{0,2})(?:${DQ}|${SQ})`],
      ['decorator', '@[A-Za-z_][\\w.]*'],
      ['number', '\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b'],
    ],
    keywords: words(
      'and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case',
    ),
    constants: words('None True False self cls'),
    builtins: words('str int float bool list dict set tuple bytes object type len range print isinstance super Optional Literal Any Union Path'),
    defines: { def: 'function', class: 'class' },
    types: true,
    name: '[A-Za-z_]\\w*',
  },
  json: {
    rules: [
      ['key', `${DQ}(?=\\s*:)`],
      ['string', DQ],
      ['comment', '//[^\\n]*|/\\*[\\s\\S]*?\\*/'],
      ['number', '-?\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b'],
    ],
    constants: words('true false null'),
    name: '[A-Za-z_]\\w*',
  },
  javascript: {
    rules: [LINE_C, ['string', `${DQ}|${SQ}|\`(?:[^\`\\\\]|\\\\.)*\``], ['decorator', '@[A-Za-z_$][\\w$.]*'], NUMBER],
    keywords: words(JS_KW),
    constants: words('true false null undefined this NaN Infinity'),
    builtins: words('console Math JSON Promise Array Object String Number Boolean Map Set WeakMap Symbol Error Date RegExp BigInt globalThis window document'),
    defines: { function: 'function', class: 'class' },
    types: true,
  },
  typescript: {
    rules: [LINE_C, ['string', `${DQ}|${SQ}|\`(?:[^\`\\\\]|\\\\.)*\``], ['decorator', '@[A-Za-z_$][\\w$.]*'], NUMBER],
    keywords: words(
      `${JS_KW} interface type enum implements namespace declare abstract private protected public readonly keyof infer is satisfies module override`,
    ),
    constants: words('true false null undefined this NaN Infinity'),
    builtins: words(
      'console Math JSON Promise Array Object String Number Boolean Map Set WeakMap Symbol Error Date RegExp BigInt globalThis string number boolean unknown never any void Record Partial Readonly',
    ),
    defines: { function: 'function', class: 'class', interface: 'class', type: 'class', enum: 'class' },
    types: true,
  },
  c: {
    rules: [['meta', '^[ \\t]*#[ \\t]*\\w+'], LINE_C, ['string', `${DQ}|${CHAR}`], NUMBER],
    keywords: words(C_KW),
    constants: words('NULL true false'),
    builtins: words('printf fprintf malloc calloc realloc free size_t memcpy memset strlen strcmp FILE'),
    defines: C_DEFINES,
    types: true,
  },
  cpp: {
    rules: [['meta', '^[ \\t]*#[ \\t]*\\w+'], LINE_C, ['string', `${DQ}|${CHAR}`], NUMBER],
    keywords: words(
      `${C_KW} alignas alignof catch class constexpr consteval const_cast decltype delete dynamic_cast explicit export friend mutable namespace new noexcept operator private protected public reinterpret_cast static_assert static_cast template this thread_local throw try typeid typename using virtual co_await co_return co_yield concept requires override final`,
    ),
    constants: words('nullptr NULL true false'),
    builtins: words('std string vector map set unordered_map array optional cout cerr endl unique_ptr shared_ptr make_unique make_shared size_t'),
    defines: C_DEFINES,
    types: true,
  },
  java: {
    rules: [LINE_C, ['string', `"""[\\s\\S]*?"""|${DQ}|${CHAR}`], ['decorator', '@[A-Za-z_][\\w.]*'], NUMBER],
    keywords: words(
      'abstract assert boolean break byte case catch char class continue default do double else enum extends final finally float for if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while var record yield sealed permits',
    ),
    constants: words('true false null'),
    builtins: words('String System Object Integer Long Double Boolean List Map Set Optional Exception RuntimeException'),
    defines: { class: 'class', interface: 'class', enum: 'class', record: 'class' },
    types: true,
  },
  go: {
    rules: [LINE_C, ['string', `${DQ}|\`[^\`]*\`|${CHAR}`], NUMBER],
    keywords: words(
      'break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var',
    ),
    constants: words('true false nil iota'),
    builtins: words(
      'append cap close complex copy delete imag len make new panic print println real recover string int int8 int16 int32 int64 uint uint8 uint16 uint32 uint64 byte rune error bool float32 float64 any',
    ),
    defines: { func: 'function', type: 'class' },
    types: true,
  },
  rust: {
    rules: [
      LINE_C,
      ['string', 'b?r#*"[\\s\\S]*?"#*|b?"(?:[^"\\\\]|\\\\.)*"'],
      ['string', `b?${CHAR}`],
      ['type', "'[A-Za-z_]\\w*\\b(?!')"],
      ['decorator', '#!?\\[[^\\]\\n]*\\]'],
      ['builtin', '\\b[A-Za-z_]\\w*!(?=\\s*[\\[({])'],
      NUMBER,
    ],
    keywords: words(
      'as async await break const continue crate dyn else enum extern fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait type unsafe use where while',
    ),
    constants: words('true false None Some Ok Err'),
    builtins: words('Vec String Option Result Box Rc Arc HashMap str usize isize u8 u16 u32 u64 i8 i16 i32 i64 f32 f64 bool char'),
    defines: { fn: 'function', struct: 'class', enum: 'class', trait: 'class', type: 'class' },
    types: true,
  },
  shell: {
    rules: [
      ['comment', '(?:^|(?<=\\s))#[^\\n]*'],
      ['string', `"(?:[^"\\\\]|\\\\.)*"|'[^']*'`],
      ['builtin', '\\$(?:\\{[^}\\n]*\\}|\\w+|[@*#?$!0-9-])'],
      ['number', '\\b\\d+\\b'],
    ],
    keywords: words('if then else elif fi for while until do done case esac in function select return local export readonly declare set unset shift break continue exit source alias'),
    builtins: words('echo cd printf read test eval exec trap pwd'),
    name: '[A-Za-z_][\\w-]*',
  },
  toml: {
    rules: [
      ['comment', '#[^\\n]*'],
      ['class', '^[ \\t]*\\[\\[?[^\\]\\n]*\\]\\]?'],
      ['key', '^[ \\t]*[A-Za-z0-9_.\\-"\']+(?=[ \\t]*=)'],
      ['string', `"""[\\s\\S]*?"""|'''[\\s\\S]*?'''|${DQ}|'[^'\\n]*'`],
      ['number', '\\d{4}-\\d{2}-\\d{2}(?:[T ]\\d{2}:\\d{2}(?::\\d{2}(?:\\.\\d+)?)?(?:Z|[+-]\\d{2}:\\d{2})?)?'],
      ['number', '[+-]?\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b'],
    ],
    constants: words('true false inf nan'),
    name: '[A-Za-z_]\\w*',
  },
  yaml: {
    rules: [
      ['comment', '(?:^|(?<=\\s))#[^\\n]*'],
      ['meta', '^(?:---|\\.\\.\\.)(?=\\s|$)'],
      ['key', '[A-Za-z0-9_.\\-/]+(?=:(?:[ \\t]|$))'],
      ['string', `${DQ}|'(?:[^'\\n]|'')*'`],
      ['decorator', '[&*][\\w-]+'],
      ['number', '[+-]?\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b'],
    ],
    constants: words('true false null yes no on off True False Null'),
    name: '[A-Za-z_]\\w*',
  },
  sql: {
    rules: [['comment', '--[^\\n]*|/\\*[\\s\\S]*?\\*/'], ['string', "'(?:[^']|'')*'"], ['key', '"(?:[^"]|"")*"'], ['number', '\\b\\d+(?:\\.\\d+)?\\b']],
    keywords: words(
      'select from where and or not insert into values update set delete create table drop alter add column index primary key foreign references join left right inner outer full cross on as group by order having limit offset union all distinct case when then else end is in exists between like returning with view default unique constraint if begin commit rollback transaction asc desc',
    ),
    constants: words('true false null'),
    builtins: words('count sum avg min max coalesce cast lower upper now integer int text varchar char boolean date timestamp real numeric bigint serial float double'),
    caseless: true,
    name: '[A-Za-z_]\\w*',
  },
  xml: {
    rules: [
      ['comment', '<!--[\\s\\S]*?-->'],
      ['meta', '<\\?[\\s\\S]*?\\?>|<!\\[CDATA\\[[\\s\\S]*?\\]\\]>|<![A-Za-z][^>]*>'],
      ['tag', '</?[A-Za-z_][\\w:.-]*|/?>'],
      ['attribute', '[A-Za-z_:][\\w:.-]*(?=\\s*=\\s*["\'])'],
      ['string', '(?<==\\s*)(?:"[^"]*"|\'[^\']*\')'],
      ['constant', '&#?\\w+;'],
    ],
    name: null,
  },
  diff: {
    rules: [
      ['meta', '^(?:diff |index |--- |\\+\\+\\+ |@@)[^\\n]*'],
      ['inserted', '^\\+[^\\n]*'],
      ['deleted', '^-[^\\n]*'],
    ],
    name: null,
  },
};

/** The other names and the file extensions of each language. */
const ALIASES: Record<string, Language> = {
  py: 'python', python3: 'python', pyi: 'python', pyw: 'python',
  jsonc: 'json', jsonl: 'json', json5: 'json', geojson: 'json',
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript', node: 'javascript',
  ts: 'typescript', tsx: 'typescript', mts: 'typescript', cts: 'typescript',
  h: 'c',
  'c++': 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp', hh: 'cpp', hxx: 'cpp',
  golang: 'go',
  rs: 'rust',
  sh: 'shell', bash: 'shell', zsh: 'shell', ksh: 'shell', shellscript: 'shell',
  ini: 'toml', cfg: 'toml',
  yml: 'yaml',
  html: 'xml', htm: 'xml', xhtml: 'xml', svg: 'xml', plist: 'xml', xsd: 'xml', xsl: 'xml',
  patch: 'diff',
};

/** The language `hint` names: a language's name, another name of it, a file name or its extension; '' for any other. */
export function languageOf(hint: string | null | undefined): Language | '' {
  const h = String(hint || '').trim().toLowerCase().replace(/^.*\//, '');
  const known = (s: string): Language | '' => ((LANGUAGES as readonly string[]).includes(s) ? (s as Language) : (ALIASES[s] ?? ''));
  return known(h) || (h.includes('.') ? known(h.replace(/^.*\./, '')) : '');
}

const compiled = new Map<Language, RegExp>();

function patternOf(lang: Language): RegExp {
  let re = compiled.get(lang);
  if (!re) {
    const g = GRAMMARS[lang];
    const parts = g.rules.map(([, src]) => `(${src})`);
    const name = g.name === undefined ? NAME : g.name;
    if (name) parts.push(`(${name})`);
    re = new RegExp(parts.join('|'), 'gm');
    compiled.set(lang, re);
  }
  return re;
}

/** The type of a name: a keyword, a constant, a function's or a type's own name, a built-in or a type; '' for any other. */
function nameType(g: Grammar, word: string, prev: string): TokenType {
  const w = g.caseless ? word.toLowerCase() : word;
  if (g.keywords?.has(w)) return 'keyword';
  if (g.constants?.has(w)) return 'constant';
  const defined = g.defines?.[prev];
  if (defined) return defined;
  if (g.builtins?.has(w)) return 'builtin';
  if (g.types && /^[A-Z]\w*$/.test(word) && word.length > 1 && /[a-z]/.test(word)) return 'type';
  return '';
}

/** `code` as tokens of `hint`'s language (`languageOf`); the whole text as one plain token for any other. */
export function tokenize(code: string, hint?: string | null): CodeToken[] {
  const lang = languageOf(hint);
  if (!lang || !code) return code ? [{ text: code, type: '' }] : [];
  const g = GRAMMARS[lang];
  const re = patternOf(lang);
  const out: CodeToken[] = [];
  const push = (text: string, type: TokenType) => {
    if (!text) return;
    const last = out[out.length - 1];
    if (last && last.type === type) last.text += text;
    else out.push({ text, type });
  };
  let at = 0;
  let prev = '';
  re.lastIndex = 0;
  for (let m = re.exec(code); m; m = re.exec(code)) {
    if (!m[0]) {
      re.lastIndex++;
      continue;
    }
    const gap = code.slice(at, m.index);
    if (/\S/.test(gap)) prev = '';
    push(gap, '');
    at = re.lastIndex;
    const rule = m.findIndex((x, i) => i > 0 && x !== undefined) - 1;
    if (rule < g.rules.length) {
      push(m[0], g.rules[rule]![0]);
      prev = '';
    } else {
      push(m[0], nameType(g, m[0], prev));
      prev = m[0];
    }
  }
  push(code.slice(at), '');
  return out;
}

/** The classes of a token's type in the markup (`prose` colours them). */
const CLASS: Record<Exclude<TokenType, ''>, string> = {
  comment: 'hl-c',
  doc: 'hl-s hl-doc',
  string: 'hl-s',
  number: 'hl-n',
  keyword: 'hl-k',
  constant: 'hl-k hl-const',
  builtin: 'hl-b',
  type: 'hl-t',
  function: 'hl-f',
  class: 'hl-cls',
  decorator: 'hl-d',
  key: 'hl-key',
  tag: 'hl-tag',
  attribute: 'hl-attr',
  inserted: 'hl-ins',
  deleted: 'hl-del',
  meta: 'hl-meta',
};

/** Tokens as escaped HTML, each but plain text in a `<span>` of its type's class. */
export function tokensHtml(tokens: readonly CodeToken[]): string {
  return tokens.map((t) => (t.type ? `<span class="${CLASS[t.type]}">${esc(t.text)}</span>` : esc(t.text))).join('');
}

/** Tokens split into lines at each line break: a token across lines becomes one piece per line. */
export function tokenLines(tokens: readonly CodeToken[]): CodeToken[][] {
  const lines: CodeToken[][] = [[]];
  for (const t of tokens) {
    const parts = t.text.split('\n');
    parts.forEach((text, i) => {
      if (i > 0) lines.push([]);
      if (text) lines[lines.length - 1]!.push({ text, type: t.type });
    });
  }
  return lines;
}

/** Highlighted, escaped HTML. `hint` is a language (`python`), another name of it, or a file name (`schema.py`); anything unknown is plain. */
export function highlight(code: string, hint?: string | null): string {
  return tokensHtml(tokenize(code, hint));
}

/** Python as highlighted, escaped HTML. */
export const hlPython = (src: string): string => highlight(src, 'python');

/** JSON as highlighted, escaped HTML. */
export const hlJson = (src: string): string => highlight(src, 'json');
