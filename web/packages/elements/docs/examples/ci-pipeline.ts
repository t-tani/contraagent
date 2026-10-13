// A whole page from the generic elements: one run of a made-up CI pipeline.
// A theme switch, stat tiles, a sortable table of jobs, and a layered graph of
// the steps (a shard is a series; the end-to-end tests repeat in a retry loop),
// with a detail panel of the page's own beside them. The page holds the data
// and the state (the theme, the selection, the order), and answers the events.
import '@contraagent/elements/segmented/define'; // <cae-segmented>
import '@contraagent/elements/tiles/define'; // <cae-stat-tiles>
import '@contraagent/elements/data-table/define'; // <cae-data-table>
import '@contraagent/elements/graph/define'; // <cae-layered-graph>
import { adoptThemes } from '@contraagent/elements/themes';
import { fmtDur, pill, type StateStyles } from '@contraagent/elements';
import { sortRows, type CaeDataTable, type DataColumn } from '@contraagent/elements/data-table';
import type { GraphInput, GraphMark, GraphNodeInput } from '@contraagent/elements/graph';
import type { StatTile } from '@contraagent/elements/tiles';

// ---- The data: a step is a node, a job is one run of a step (or of one shard of it).

type State = 'done' | 'failed' | 'running' | 'queued';

interface Job {
  id: string;
  step: string;
  /** The shard ('1' to '3'), or null for a step that runs once. */
  shard: string | null;
  /** The pass of the retry loop it ran in (1 outside the loop). */
  pass: number;
  state: State;
  seconds: number;
  runner: string;
}

const steps = [
  { id: 'lint', label: 'lint', loop: false },
  { id: 'unit', label: 'unit tests', loop: false },
  { id: 'build', label: 'build', loop: false },
  { id: 'e2e', label: 'e2e tests', loop: true },
  { id: 'triage', label: 'triage failures', loop: true },
  { id: 'deploy', label: 'deploy preview', loop: false },
];
const shards = ['1', '2', '3'];

const job = (step: string, shard: string | null, pass: number, state: State, seconds: number, runner: string): Job => ({
  id: `${step}${shard ? `/${shard}` : ''}#${pass}`,
  step,
  shard,
  pass,
  state,
  seconds,
  runner,
});

const jobs: Job[] = [
  job('lint', null, 1, 'done', 41, 'small-1'),
  job('unit', '1', 1, 'done', 188, 'large-1'),
  job('unit', '2', 1, 'done', 203, 'large-2'),
  job('unit', '3', 1, 'done', 176, 'large-3'),
  job('build', null, 1, 'done', 315, 'large-1'),
  job('e2e', '1', 1, 'done', 402, 'large-2'),
  job('e2e', '2', 1, 'failed', 377, 'large-3'),
  job('e2e', '3', 1, 'done', 395, 'large-1'),
  job('triage', null, 1, 'done', 12, 'small-1'),
  job('e2e', '2', 2, 'done', 381, 'large-2'),
  job('triage', null, 2, 'done', 9, 'small-1'),
  job('deploy', null, 1, 'running', 74, 'deploy-1'),
];

// ---- What each state looks like: a word, a tone, a shape (the legend follows this order).

const states: StateStyles = {
  done: { label: 'done', tone: 'done', shape: 'round', rank: 0 },
  queued: { label: 'queued', tone: 'muted', shape: 'ring', rank: 1 },
  running: { label: 'running', tone: 'running', shape: 'round', rank: 2 },
  failed: { label: 'failed', tone: 'failed', shape: 'square', rank: 3 },
};
const toneOf = (s: State) => states[s]!.tone;
const jobName = (j: Job) => `${steps.find((s) => s.id === j.step)!.label}${j.shard ? ` shard ${j.shard}` : ''}`;

// ---- The graph: a mark per shard (or one loose mark), the last pass's state, the passes as a badge.

/** The id of a mark: a step's shard, or the step's single job. */
const markId = (j: Job) => `${j.step}/${j.shard ?? '-'}`;

function mark(runs: Job[]): GraphMark {
  const last = runs[runs.length - 1]!;
  const passes = runs.length > 1 ? `${runs.length} passes` : '1 pass';
  return { id: markId(last), state: last.state, label: `${jobName(last)} | ${last.state} | ${passes}`, tip: jobName(last), badge: runs.length > 1 ? String(runs.length) : undefined };
}

function node(step: (typeof steps)[number]): GraphNodeInput {
  const own = jobs.filter((j) => j.step === step.id);
  const runsOf = (shard: string | null) => own.filter((j) => j.shard === shard);
  const sharded = own.some((j) => j.shard);
  const marks = sharded ? shards.map((s) => (runsOf(s).length ? mark(runsOf(s)) : null)) : [];
  const loose = sharded ? [] : [mark(runsOf(null))];
  // `counts` and `progress` ("2/3") default to what the marks say.
  // A job that failed in an earlier pass is not in the marks: the line under them names it.
  const failed = own.filter((j) => j.state === 'failed').length;
  return {
    id: step.id,
    label: step.label,
    cluster: step.loop ? 'retry' : null,
    marks,
    loose,
    notes: failed ? [{ text: `${failed} failed ${failed === 1 ? 'job' : 'jobs'}`, tone: 'failed' }] : [],
  };
}

const graph: GraphInput = {
  series: shards,
  nodes: steps.map(node),
  clusters: [{ id: 'retry', parent: null, label: 'retry loop', note: 'up to 3 passes', cycle: true }],
  edges: [
    { from: 'lint', to: 'build', style: 'solid', weight: 1, ranks: true },
    { from: 'unit', to: 'build', style: 'solid', weight: 3, ranks: true },
    { from: 'build', to: 'e2e', style: 'solid', weight: 3, ranks: true },
    { from: 'e2e', to: 'triage', style: 'solid', weight: 3, ranks: true },
    // The next pass: from triage back to the tests. It does not set the layers.
    { from: 'triage', to: 'e2e', style: 'solid', weight: 1, ranks: false },
    { from: 'triage', to: 'deploy', style: 'solid', weight: 1, ranks: true },
  ],
  stubs: [{ id: 'push', label: 'push to main', to: 'lint', style: 'solid', weight: 1 }],
};

// ---- The table: a row per job; every column sorts.

const columns: DataColumn<Job>[] = [
  { id: 'job', header: 'Job', rowHeader: true, cell: jobName, sortable: true },
  { id: 'pass', header: 'Pass', align: 'end', width: '72px', cell: (j) => j.pass, compare: (a, b) => a.pass - b.pass },
  { id: 'state', header: 'State', width: '120px', cell: (j) => pill({ text: j.state, tone: toneOf(j.state) }), compare: (a, b) => states[a.state]!.rank - states[b.state]!.rank },
  { id: 'time', header: 'Time', align: 'end', width: '96px', cell: (j) => fmtDur(j.seconds), compare: (a, b) => a.seconds - b.seconds },
  { id: 'runner', header: 'Runner', width: '120px', cell: (j) => j.runner, sortable: true },
];

// ---- The tiles.

const failed = jobs.filter((j) => j.state === 'failed');
const passes = Math.max(...jobs.map((j) => j.pass));
const count = (s: State) => jobs.filter((j) => j.state === s).length;
const tiles: StatTile[] = [
  { id: 'jobs', label: 'Jobs', value: jobs.length, sub: [[`${count('done')} done`, `${count('running')} running`]] },
  { id: 'failed', label: 'Failed jobs', value: failed.length, tone: failed.length ? 'failed' : undefined, sub: [failed.length ? failed.map((j) => `${jobName(j)}, pass ${j.pass}`) : ['All jobs passed']] },
  { id: 'passes', label: 'Passes of the retry loop', value: passes, sub: [['Up to 3']] },
  { id: 'time', label: 'Job time', value: fmtDur(jobs.reduce((t, j) => t + j.seconds, 0)), tip: 'Sum over all jobs' },
];

// ---- The page's own styles. Its colours are the theme's, so the page changes with the switch.

const css = `
.ci-page {
  background: var(--ca-bg);
  color: var(--ca-text);
  font: 14px/1.45 system-ui, sans-serif;
  padding: 16px;
  display: grid;
  gap: 16px;
  container-type: inline-size;
}
.ci-page header { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.ci-page h2 { font-size: 18px; margin: 0; flex: 1; color: var(--ca-text); }
.ci-page h3 { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--ca-text-secondary); }
.ci-page .body { display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr) 260px; align-items: start; }
.ci-page .main { display: grid; gap: 16px; min-width: 0; }
.ci-page aside { background: var(--ca-card); border: 1px solid var(--ca-line); border-radius: 8px; padding: 12px; position: sticky; top: 0; }
.ci-page dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 0; }
.ci-page dt { color: var(--ca-text-muted); }
.ci-page dd { margin: 0; }
@container (max-width: 760px) { .ci-page .body { grid-template-columns: minmax(0, 1fr); } }
`;

// ---- The page: build it, then answer the events.

export function mount(host: HTMLElement): void {
  adoptThemes(document);
  host.dataset['caTheme'] = 'contraagent-dark';

  const page = document.createElement('div');
  page.className = 'ci-page';
  page.innerHTML = `<style>${css}</style>
    <header><h2>web-app | pipeline 482 | main</h2></header>
    <div class="body">
      <div class="main">
        <section><h3>Pipeline</h3></section>
        <section></section>
      </div>
      <aside aria-live="polite"><h3>Selected</h3><div class="detail">No selection</div></aside>
    </div>`;
  const [graphBox, tableBox] = page.querySelectorAll('section');
  const detail = page.querySelector<HTMLElement>('.detail')!;

  // The theme: `data-ca-theme` on the box that holds the page.
  const theme = document.createElement('cae-segmented');
  theme.label = 'Theme';
  theme.options = [
    { value: 'contraagent-dark', label: 'Dark' },
    { value: 'contraagent-light', label: 'Light' },
    { value: 'high-contrast', label: 'High contrast' },
  ];
  theme.value = 'contraagent-dark';
  theme.addEventListener('cae-change', (e) => {
    theme.value = e.detail.value;
    host.dataset['caTheme'] = e.detail.value;
  });
  page.querySelector('header')!.append(theme);

  const stats = document.createElement('cae-stat-tiles');
  stats.columns = 4;
  stats.tiles = tiles;
  page.querySelector('header')!.after(stats);

  const table = document.createElement('cae-data-table') as CaeDataTable<Job>;
  table.caption = 'Jobs of pipeline 482';
  table.columns = columns;
  table.rowKey = (j) => j.id;
  table.rows = jobs;
  table.addEventListener('cae-sort', (e) => {
    table.sort = e.detail;
    table.rows = sortRows(jobs, columns, e.detail);
  });
  tableBox!.append(table);

  const view = document.createElement('cae-layered-graph');
  view.key = 'pipeline-482'; // a new key is a new graph: the frame shows all of it again
  view.graph = graph;
  view.states = states;
  view.strings = { cycle: 'next pass', badge: 'number of passes' };
  view.showInspector = false; // the panel beside the graph describes the selection
  graphBox!.append(view);

  /** The selection: the graph shows it, the panel describes it. */
  const select = (id: string | null) => {
    view.selected = id;
    detail.replaceChildren(describe(id));
  };
  view.addEventListener('cae-select', (e) => select(e.detail.id));
  // A row of the table selects its job's mark in the graph.
  table.addEventListener('cae-activate', (e) => select(markId(jobs.find((j) => j.id === e.detail.id)!)));

  host.replaceChildren(page);
}

/** The panel's content for a mark, a node or the loop. */
function describe(id: string | null): Node {
  const runs = jobs.filter((j) => markId(j) === id);
  const step = steps.find((s) => s.id === id);
  let title = 'No selection';
  let rows: [string, string][] = [];
  if (runs.length) {
    const last = runs[runs.length - 1]!;
    title = jobName(last);
    rows = [['State', last.state], ['Passes', String(runs.length)], ...runs.map((j): [string, string] => [`Pass ${j.pass}`, `${j.state} | ${fmtDur(j.seconds)} | ${j.runner}`])];
  } else if (step) {
    const own = jobs.filter((j) => j.step === step.id);
    title = step.label;
    rows = [['Jobs', String(own.length)], ['Failed', String(own.filter((j) => j.state === 'failed').length)], ['Time', fmtDur(own.reduce((t, j) => t + j.seconds, 0))]];
  } else if (id === 'retry') {
    title = 'retry loop';
    rows = [['Passes', `${passes} of up to 3`], ['Rerun', jobs.filter((j) => j.pass > 1 && j.shard).map(jobName).join(', ')]];
  }
  const box = document.createElement('div');
  const h = document.createElement('strong');
  h.textContent = title;
  const dl = document.createElement('dl');
  for (const [k, v] of rows) {
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = k;
    dd.textContent = v;
    dl.append(dt, dd);
  }
  box.append(h, dl);
  return box;
}
