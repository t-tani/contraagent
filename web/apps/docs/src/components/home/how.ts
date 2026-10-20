// What the landing page's "how it works" scene shows, read when the site renders:
// the CLI's own output on the demo pipeline of the package's examples (written by
// scripts/landing.py into src/fixtures/landing-outputs.json), the code of that
// pipeline quoted from the file, and the demo run's figures. Nothing here runs a command.
import type { JournalRow } from '@contraagent/api';
import fixture from '../../fixtures/demo-run.json';
import outputs from '../../fixtures/landing-outputs.json';
import { repoFile } from '../../lib/repo';
import { highlight } from './python';
import { TASKS } from './timeline';

/** The demo's flow arguments, as the scene's commands give them (scripts/landing.py has the same; a test checks). */
export const KWARGS = '{"units": ["alpha", "beta"]}';

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
  const parts = [lines(file, 'class Summary(BaseModel)', 'points: list[str]'), lines(file, 'summarize = agent_task(', ')'), lines(file, 'def docs(', 'return await report(')];
  const quoted: Line[] = [];
  for (const p of parts) {
    if (quoted.length) quoted.push({ n: 0, html: '' });
    quoted.push(...p);
  }
  const html = highlight(quoted.map((l) => l.html));

  const journal = fixture.journal as unknown as JournalRow[];
  const byEnd = [...journal].sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  const last = new Map(byEnd.map((r) => [r.key, r]));
  return {
    ...outputs,
    code: quoted.map((l, i) => ({ n: l.n, html: html[i] })),
    marks: [...last.values()].map((r) => ({ agent: r.executor === 'agent', corrected: (r.rounds ?? 1) > 1, switched: (r.hops ?? []).length > 1 })),
    done: fixture.plan.nodes.filter((n) => n.state === 'done').length,
    total: fixture.plan.nodes.length,
    corrections: journal.filter((r) => (r.rounds ?? 1) > 1).length,
    switches: journal.filter((r) => (r.hops ?? []).length > 1).length,
  };
}
