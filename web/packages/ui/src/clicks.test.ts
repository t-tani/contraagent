// Every `@click` in the templates of both packages is on an element the keyboard
// reaches: a button, a link or a form control, an element with a role and a
// `tabindex`, or one of the cases below, each with the reason a keyboard does
// not need it.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from web/.
const WEB = process.cwd();
const ROOTS = ['packages/ui/src', 'packages/elements/src'];

/** Clickable elements that are not themselves keyboard targets, by `file|tag.class`, and why that is right. */
const ALLOWED: Record<string, string> = {
  'packages/ui/src/elements/overview/ca-overview.ts|div.fl': 'a problem row: its name is a button that opens the same task',
  'packages/ui/src/elements/lists/ca-procs-view.ts|div.fl': 'a launch row: its name is a button that opens the same task',
  'packages/ui/src/elements/shell/ca-run-picker.ts|div.':
    'an option of a listbox: the focus stays on the search field (a combobox), which names the active option with aria-activedescendant',
  'packages/elements/src/graph/views/dag.ts|div.frame': 'the graph background: clears the selection, which Escape does from the keyboard',
  'packages/elements/src/graph/views/node-table.ts|div.frame': 'the table background: clears the selection, which Escape does from the keyboard',
  'packages/elements/src/graph/views/dag.ts|section.cluster': 'a cluster: its name is a button that selects it',
  'packages/elements/src/graph/views/dag.ts|section.node': 'a node: its name is a button that selects it',
  'packages/elements/src/graph/views/node-table.ts|tr.': 'a row of the table: its name is a button that selects it',
  'packages/elements/src/table/data-table.ts|tbody.': 'the rows (one listener for all): one tab stop, the arrow keys move between them and Enter opens one',
};

const INTERACTIVE = new Set(['button', 'a', 'input', 'select', 'textarea', 'summary']);

function sources(dir: string): string[] {
  const abs = join(WEB, dir);
  if (!existsSync(abs)) return [];
  return readdirSync(abs).flatMap((name) => {
    const rel = `${dir}/${name}`;
    return statSync(join(WEB, rel)).isDirectory() ? sources(rel) : /(?<!\.test)\.ts$/.test(name) ? [rel] : [];
  });
}

interface Click {
  file: string;
  line: number;
  /** `tag.class`: the element's tag and the first word of its class attribute ('' when that is an expression). */
  what: string;
  /** The tag's text up to `@click`. */
  tag: string;
}

/** Each `@click=` in `file`, with the element it is on. */
function clicksOf(file: string): Click[] {
  const text = readFileSync(join(WEB, file), 'utf8');
  return [...text.matchAll(/@click=/g)].map((m) => {
    const before = text.slice(0, m.index);
    const open = [...before.matchAll(/<([a-z][\w-]*)\b/g)].at(-1);
    const tag = open ? before.slice(open.index) : '';
    const cls = /\bclass=["']?([a-z][^\s"']*)?/.exec(tag)?.[1] ?? '';
    return { file, line: before.split('\n').length, what: `${open?.[1] ?? '?'}.${cls}`, tag };
  });
}

const reachable = (c: Click): boolean =>
  INTERACTIVE.has(c.what.split('.')[0]!) || (/\brole=/.test(c.tag) && /\btabindex=/.test(c.tag));

describe('@click targets', () => {
  const clicks = ROOTS.flatMap(sources).flatMap(clicksOf);

  it('finds the templates', () => {
    expect(clicks.length).toBeGreaterThan(20);
  });

  it('are buttons, links, controls, focusable roles, or allowed with a reason', () => {
    const bad = clicks.filter((c) => !reachable(c) && !ALLOWED[`${c.file}|${c.what}`]).map((c) => `${c.file}:${c.line} <${c.what}>`);
    expect(bad).toEqual([]);
  });

  it('allows only cases that exist', () => {
    const seen = new Set(clicks.map((c) => `${c.file}|${c.what}`));
    expect(Object.keys(ALLOWED).filter((k) => !seen.has(k))).toEqual([]);
  });
});
