// A page that uses one generic component and nothing else of contraagent: a
// layered graph of a hand-written build, from `@contraagent/elements/graph/define`.
// consumer.test.mjs builds it as an npm consumer would and checks what it holds.
import '@contraagent/elements/graph/define';
import type { GraphInput, GraphMark, GraphNodeInput } from '@contraagent/elements/graph';
import type { StateStyles } from '@contraagent/elements/primitives';

const states: StateStyles = {
  ok: { label: 'ok', tone: 'done', shape: 'round', rank: 0 },
  broken: { label: 'broken', tone: 'failed', shape: 'square', rank: 2 },
  queued: { label: 'queued', tone: 'neutral', shape: 'ring', rank: 1 },
};

const series = ['linux', 'mac'];

function node(id: string, looks: string[]): GraphNodeInput {
  const marks: GraphMark[] = series.map((s, i) => ({ id: `${id}#${s}`, state: looks[i] ?? 'queued', label: `${id} on ${s}` }));
  const counts = Object.fromEntries(Object.keys(states).map((k) => [k, marks.filter((m) => m.state === k).length]));
  const done = counts['ok'] ?? 0;
  return { id, label: id, cluster: null, marks, loose: [], counts, progress: { done, total: marks.length, label: `${done} of ${marks.length} ok` } };
}

const graph: GraphInput = {
  series,
  nodes: [node('compile', ['ok', 'ok']), node('test', ['ok', 'broken']), node('package', ['queued', 'queued'])],
  clusters: [],
  edges: [
    { from: 'compile', to: 'test', style: 'solid', weight: 1, ranks: true },
    { from: 'test', to: 'package', style: 'solid', weight: 1, ranks: true },
  ],
  stubs: [],
};

const el = document.createElement('cae-layered-graph');
el.graph = graph;
el.states = states;
el.key = 'build';
el.addEventListener('cae-select', (e) => (el.selected = e.detail.id));
document.body.append(el);
