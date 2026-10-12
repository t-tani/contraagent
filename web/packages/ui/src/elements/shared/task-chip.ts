// A task named in a list, as a chip of its own: the name keeps its `kind · unit`
// form without a separator between names, and a click opens the task.
import { isPython } from '@contraagent/api';
import { html, type TemplateResult } from 'lit';
import { emit } from '../../events.js';

/**
 * `name` as a chip that sends `ca-open-task` for `task` (a Python task opens on its
 * output). A task with no key (a running Python task) is a chip that opens nothing.
 */
export function taskChip(from: EventTarget, name: string, task: { key: string; executor?: string }): TemplateResult {
  if (!task.key) return html`<span class="taskchip">${name}</span>`;
  const open = (e: Event): void => {
    e.stopPropagation(); // the row it sits in may open another task
    emit(from, 'ca-open-task', { key: task.key, ...(isPython(task) ? { view: 'output' as const } : {}) });
  };
  return html`<button type="button" class="taskchip" title=${task.key} @click=${open}>${name}</button>`;
}
