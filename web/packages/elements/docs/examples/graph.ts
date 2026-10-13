// A layered graph: a hand-written build pipeline of three steps, the last two in a
// cluster that repeats (a retry loop), one mark per service in each step. The host
// keeps the selection and the order, and answers the events.
import '@contraagent/elements/graph/define';
import type { GraphInput, GraphMark } from '@contraagent/elements/graph';
import type { StateStyles } from '@contraagent/elements/primitives';

const states: StateStyles = {
  ok: { label: 'ok', tone: 'done', shape: 'round', rank: 0 },
  busy: { label: 'busy', tone: 'running', shape: 'round', rank: 2 },
  broken: { label: 'broken', tone: 'failed', shape: 'square', rank: 3 },
  queued: { label: 'queued', tone: 'neutral', shape: 'ring', rank: 1 },
};

const services = ['api', 'web', 'worker'];

/** One mark per service: its id is unique in the graph, so it is what the graph selects. */
const marks = (step: string, looks: string[]): GraphMark[] =>
  services.map((s, i) => ({ id: `${step}#${s}`, state: looks[i] ?? 'queued', label: `${step} · ${s} | ${looks[i] ?? 'queued'}`, tip: `${step} · ${s}` }));

const node = (id: string, label: string, looks: string[], cluster: string | null) => {
  const ms = marks(id, looks);
  const counts = Object.fromEntries(Object.keys(states).map((k) => [k, ms.filter((m) => m.state === k).length]));
  return { id, label, cluster, marks: ms, loose: [], counts, progress: { done: counts['ok'] ?? 0, total: ms.length, label: `${counts['ok'] ?? 0} of ${ms.length} ok` } };
};

const graph: GraphInput = {
  series: services,
  nodes: [
    node('build', 'build', ['ok', 'ok', 'ok'], null),
    node('test', 'test', ['ok', 'broken', 'ok'], 'retry'),
    node('deploy', 'deploy', ['busy', 'queued', 'ok'], 'retry'),
  ],
  clusters: [{ id: 'retry', parent: null, label: 'retry', note: 'up to 3 rounds', cycle: true }],
  edges: [
    { from: 'build', to: 'test', style: 'solid', weight: 3, ranks: true },
    { from: 'test', to: 'deploy', style: 'solid', weight: 3, ranks: true },
    // The next round: back from deploy to test; it does not set the layers.
    { from: 'deploy', to: 'test', style: 'solid', weight: 1, ranks: false },
  ],
  stubs: [{ id: 'commit', label: 'commit', to: 'build', style: 'solid', weight: 1 }],
};

export function mount(host: HTMLElement): void {
  const el = document.createElement('cae-layered-graph');
  el.graph = graph;
  el.states = states;
  el.key = 'pipeline';
  el.strings = { cycle: 'next round' };
  const card = document.createElement('div');
  card.slot = 'inspector';
  el.append(card);
  const shown = document.createElement('p');
  el.addEventListener('cae-select', (e) => {
    el.selected = e.detail.id;
    card.innerHTML = e.detail.id ? `<h4>${e.detail.id}</h4>` : '';
  });
  el.addEventListener('cae-activate', (e) => (shown.textContent = `Opened: ${e.detail.id}`));
  host.replaceChildren(el, shown);
}
