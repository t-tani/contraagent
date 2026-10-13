// The selection's card: what is selected, its facts and where it leads. The
// generic graph places it beside the item (its `inspector` slot).
import { isLaunched } from '@contraagent/api';
import { cycleIcon, innerIcon } from '@contraagent/elements/graph';
import { toneAttr } from '@contraagent/elements';
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { shortName } from '../../../adapters/graph/flow-index.js';
import { causeOf } from '../../../adapters/graph/input.js';
import type { Selected } from '../../../adapters/graph/selection.js';
import { doneOf, exceptions, executorWord, neighbours, notDone, stateWord, taskStateStyles, where } from '../../../adapters/graph/words.js';
import { executorIcon } from '../../../words/executor.js';
import { fmtDur, kindUnit, listText, usd } from '../../../words/format.js';
import { passCount, passLabel, passSpread, passesRan } from '../../../words/index.js';
import { primary, select, tasksOf } from './actions.js';
import type { PipelineHost } from './host.js';

/** The selection's card content, for the graph's `inspector` slot: its heading names the item, `[data-status]` its status. */
export function inspector(h: PipelineHost, s: Selected) {
  return html`<div slot="inspector" class="card">${inspect(h, s)}</div>`;
}

function inspect(h: PipelineHost, s: Selected) {
  const row = (dt: string, dd: unknown) => html`<dt>${dt}</dt><dd>${dd}</dd>`;
  const link = (text: string, go: () => void, primary = false) =>
    html`<button type="button" class="go ${primary ? 'primary' : ''}" @click=${go}>${text}</button>`;
  const clear = html`<button type="button" class="switch" @click=${() => select(h, '')}>${msg('Clear selection')}</button>`;
  const list = (xs: string[]) => (xs.length ? listText(xs) : msg('none', { id: 'none', desc: 'An empty value' }));
  if (s.type === 'box') {
    const b = s.box;
    const at = where(b.loop, b.file);
    return html`<h4 title=${b.file ? `${b.file}:${b.loop}` : nothing}>${cycleIcon(16)}${msg(str`Loop at ${at}`)}</h4>
      <dl>
        ${row(msg('Passes'), passCount(b.passes))}
        ${b.spread.length > 1 ? row(msg('Units by number of passes'), passSpread(b.spread)) : nothing}
      </dl>
      <div class="acts">${link(msg(str`Passes of the loop at ${at}`), () => primary(h, s), true)}${clear}</div>`;
  }
  if (s.type === 'node') {
    const n = s.node;
    const c = n.counts;
    const { waits, after, feeds } = neighbours(n, h.graph);
    const states = exceptions(n, h.live).map(([cls, t]) => html`<div class=${cls}>${t}</div>`);
    if (n.type === 'flow') {
      return html`<h4 title=${n.name}>${innerIcon()}${n.label}</h4>
        <div class="sub">${msg('Function')}</div>
        <dl>
          ${row(msg('Flow calls'), n.calls)}
          ${row(msg('Tasks', { id: 'tasks', desc: 'A count of tasks' }), html`${doneOf(c)}${states}`)}
          ${row(msg('Waits for'), list(waits))}
          ${after.length ? row(msg('Created after'), list(after)) : nothing}
          ${row(msg('Later tasks'), list(feeds))}
        </dl>
        <div class="acts">${link(msg(str`Inside ${n.label}`), () => primary(h, s), true)}${clear}</div>`;
    }
    return html`<h4>${n.executor && n.executor !== 'mixed' ? executorIcon(n.executor === 'python') : nothing}${n.label}</h4>
      <div class="sub">${executorWord(n)}</div>
      <dl>
        ${row(msg('Tasks', { id: 'tasks', desc: 'A count of tasks' }), html`${doneOf(c)}${states}`)}
        ${row(msg('Waits for'), list(waits))}
        ${after.length ? row(msg('Created after'), list(after)) : nothing}
        ${row(msg('Later tasks'), list(feeds))}
      </dl>
      <div class="acts">${link(msg(str`Tasks of ${n.label}`), () => primary(h, s), true)}${clear}</div>`;
  }
  const { node, mark: m, passes } = s;
  const name = kindUnit({ kind: node.label, unit: m.unit });
  const cause = !m.flow && m.state === 'blocked' ? causeOf(h)(m.key) : '';
  const status = html`<span data-status class=${m.state === 'failed' ? 'err' : m.state === 'blocked' ? 'warn' : ''}>${stateWord(m.state, h.live)}</span>`;
  const look = taskStateStyles(h.live)[m.state];
  const head = html`<h4 title=${m.flow ? msg(str`Flow call ${m.key}`) : m.key}><i class="mark" data-tone=${toneAttr(look?.tone)} data-shape=${look?.shape ?? nothing} aria-hidden="true"></i>${name}</h4>`;
  const pass = passes.length ? listText(passes.map(passLabel)) : m.passes ? passesRan(m.passes) : '';
  if (m.flow) {
    const c = m.counts;
    return html`${head}
      <dl>
        ${row(msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' }), status)}
        ${pass ? row(msg('Pass'), pass) : nothing}
        ${c ? row(msg('Tasks', { id: 'tasks', desc: 'A count of tasks' }), html`${doneOf(c)}${notDone(c, h.live).map((t) => html`<div>${t}</div>`)}`) : nothing}
        ${m.error !== undefined ? row(msg('Error'), html`<span class="err">${m.error || msg('Flow call stopped with an error')}</span>`) : nothing}
      </dl>
      <div class="acts">${link(msg(str`Inside ${shortName(m.flow)}`), () => primary(h, s), true)}${clear}</div>`;
  }
  const rows = h.journal.filter((r) => m.keys.includes(r.key));
  const ran = rows.filter(isLaunched);
  const costs = ran.map((r) => r.cost_usd).filter((x): x is number => typeof x === 'number');
  const wall = ran.reduce((a, r) => a + (r.wall_s ?? 0), 0);
  return html`${head}
    <dl>
      ${row(msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' }), cause ? html`${status}<div>${cause}</div>` : status)}
      ${pass ? row(msg('Pass'), pass) : nothing}
      ${m.count > 1 ? row(msg('Tasks', { id: 'tasks', desc: 'A count of tasks' }), msg(str`${m.count} tasks`)) : nothing}
      ${row(msg('Attempts'), ran.length || msg('none', { id: 'none', desc: 'An empty value' }))}
      ${row(msg('Time'), ran.length ? fmtDur(wall) : msg('none', { id: 'none', desc: 'An empty value' }))}
      ${row(msg('Cost'), costs.length ? usd(costs.reduce((a, x) => a + x, 0)) : '—')}
    </dl>
    <div class="acts">${link(msg('Task detail'), () => primary(h, s), true)}${node.kinds.length === 1
        ? link(msg(str`Tasks of ${node.label}`), () => tasksOf(h, node))
        : nothing}${clear}</div>`;
}
