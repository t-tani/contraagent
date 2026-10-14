// The transcript pane of `ca-task-view` when the task has no transcript; a task
// with one shows `ca-transcript` there.
import { msg } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { facts, kindUnit } from '../../../words/format.js';
import { outcomeLabel, taskStatusLabel } from '../../../words/index.js';
import { taskChip } from '../../shared/task-chip.js';
import { culprit, hadSession, stateOf, type TaskContext } from '../context.js';

/** Why there is no transcript: the task's state, or a transcript that was not saved. */
export function noTranscript(c: TaskContext): TemplateResult {
  const d = c.detail;
  const state = stateOf(c);
  if (state === 'not_started') {
    // The cause is in the verdict above; here, the state and the earlier task to open.
    const up = culprit(c);
    return html`<div class="blank notrans"><span class="ic" aria-hidden="true">⊘</span><b>${facts(msg('No transcript'), outcomeLabel(state))}</b>
      ${up ? html`<span>${msg(html`Earlier task ${taskChip(c.host, kindUnit(up), up)}`)}</span>` : nothing}</div>`;
  }
  if (hadSession(d)) {
    return html`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${msg('No transcript')}</b>
      <span>${msg('Transcript not saved (keep_transcripts = false)')}</span></div>`;
  }
  // A deferred task never ran, though the run goes on: "not run", as the tasks list says.
  const deferred = state === 'waiting' && !!c.plan?.nodes.find((n) => n.key === d.key)?.deferred;
  return html`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${facts(msg('No transcript'), deferred ? taskStatusLabel(state, false) : outcomeLabel(state))}</b></div>`;
}
