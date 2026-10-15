// What the landing page's "how it works" scene shows, made when the site is built:
// the CLI's own output (run here, on the demo pipeline of the package's examples),
// the code of that pipeline quoted from the file, and the demo run's figures.
import { execFileSync, spawnSync } from 'node:child_process';
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { JournalRow } from '@contraagent/api';
import fixture from '../../fixtures/demo-run.json';
import { REPO, repoFile } from '../../lib/repo';
import { highlight } from './python';
import { TASKS } from './timeline';

const DEMO = resolve(REPO, 'src/contraagent/docs/examples/demo');

/** The demo's flow arguments, as the scene's commands give them. */
export const KWARGS = '{"units": ["alpha", "beta"]}';

/** A command of the CLI in `cwd` (the demo's directory), and what it printed, whatever its exit status. */
function cli(args: string[], cwd = DEMO): string {
  const r = spawnSync('uv', ['run', '--quiet', '--project', REPO, ...args], { cwd, encoding: 'utf8' });
  if (r.error) throw r.error;
  return `${r.stdout}${r.stderr}`.trimEnd();
}

/** The mistakes the scene's agent makes on its first try, in a copy of the demo: the units as one string, a kind's name misspelt in the config. */
const SLIP = { kwargs: '{"units": "alpha"}', from: '[tasks.summarize]', to: '[tasks.sumarize]' };

/** `contraagent check` on a copy of the demo with those mistakes, in a directory of the system's temporary files. */
function brokenCheck(): string {
  const dir = join(tmpdir(), 'contraagent-landing', 'project');
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  cpSync(DEMO, dir, { recursive: true, filter: (src) => !src.includes('__pycache__') });
  const toml = join(dir, 'pipeline.toml');
  const text = readFileSync(toml, 'utf8');
  if (!text.includes(SLIP.from)) throw new Error(`demo pipeline.toml has no ${SLIP.from}`);
  writeFileSync(toml, text.replace(SLIP.from, SLIP.to));
  const out = cli(['contraagent', 'check', 'tasks.py:docs', '--config', 'pipeline.toml', '--stub', '--kwargs', SLIP.kwargs], dir);
  if (!/error:/.test(out) || !/warning:/.test(out)) throw new Error(`the broken copy's check did not report an error and a warning:\n${out}`);
  return out;
}

/** A quoted line of code: its number in tasks.py and its HTML. */
export interface Line { n: number; html: string }

export interface How {
  version: string;
  /** The topics `contraagent docs` lists (their titles). */
  topics: string[];
  /** `contraagent check` on the first try: its command's arguments and its output. */
  slip: { kwargs: string; from: string; to: string; output: string };
  pointer: string;
  check: string;
  /** The demo's tests on a stub agent: one line per test, then the summary pytest prints. */
  tests: string[];
  code: Line[];
  /** Every task of the demo run, in the order they finished: an agent task or a Python task, and what it went through. */
  marks: { agent: boolean; corrected: boolean; switched: boolean }[];
  done: number;
  total: number;
  corrections: number;
  switches: number;
}

/** Lines `from` to `to` of tasks.py (1-based, inclusive). */
function lines(file: string[], from: string, to: string): Line[] {
  const a = file.findIndex((l) => l.includes(from));
  const b = file.findIndex((l, i) => i >= a && l.includes(to));
  if (a < 0 || b < 0) throw new Error(`${TASKS}: no lines from ${JSON.stringify(from)} to ${JSON.stringify(to)}`);
  return file.slice(a, b + 1).map((html, i) => ({ n: a + i + 1, html }));
}

export function how(): How {
  const file = repoFile(TASKS).split('\n');
  const parts = [lines(file, 'class Summary(BaseModel)', 'points: list[str]'), lines(file, 'summarize = agent_task(', ')'), lines(file, 'def docs(', 'return (yield report(')];
  const quoted: Line[] = [];
  for (const p of parts) {
    if (quoted.length) quoted.push({ n: 0, html: '' });
    quoted.push(...p);
  }
  const html = highlight(quoted.map((l) => l.html));

  // pytest as a project without the repository's own pytest options runs it.
  const run = execFileSync('uv', ['run', '--quiet', '--project', REPO, 'pytest', 'test_demo.py', '-v', '-o', 'addopts=', '-p', 'no:cacheprovider'], {
    cwd: DEMO,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const tests = run
    .split('\n')
    .filter((l) => /^test_demo\.py::\S+ (PASSED|FAILED)/.test(l) || /^=+ \d+ (passed|failed)/.test(l))
    .map((l) => l.replace(/\s+\[\s*\d+%\]$/, '').replace(/^=+ | =+$/g, ''));
  if (!tests.some((l) => /\d+ passed/.test(l)) || tests.some((l) => /FAILED|failed/.test(l))) throw new Error(`test_demo.py did not pass:\n${run}`);

  const journal = fixture.journal as unknown as JournalRow[];
  const byEnd = [...journal].sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  const last = new Map(byEnd.map((r) => [r.key, r]));
  const docs = cli(['contraagent', 'docs']);
  const topics = [...docs.matchAll(/^- \[([^\]]+)\]\(/gm)].map((m) => m[1]);
  if (topics.length < 5) throw new Error('`contraagent docs` lists no topics');
  return {
    version: cli(['contraagent', '--version']),
    topics,
    slip: { ...SLIP, output: brokenCheck() },
    pointer: cli(['contraagent', 'docs', '--pointer']),
    check: cli(['contraagent', 'check', 'tasks.py:docs', '--config', 'pipeline.toml', '--stub', '--kwargs', KWARGS]),
    tests,
    code: quoted.map((l, i) => ({ n: l.n, html: html[i] })),
    marks: [...last.values()].map((r) => ({ agent: r.executor === 'agent', corrected: (r.rounds ?? 1) > 1, switched: (r.hops ?? []).length > 1 })),
    done: fixture.plan.nodes.filter((n) => n.state === 'done').length,
    total: fixture.plan.nodes.length,
    corrections: journal.filter((r) => (r.rounds ?? 1) > 1).length,
    switches: journal.filter((r) => (r.hops ?? []).length > 1).length,
  };
}
