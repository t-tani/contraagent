// The definition pane of `ca-task-view`: the task's kind, as `ca-definition` shows it.
import { html, type TemplateResult } from 'lit';
import '../../shared/ca-definition.js';
import type { TaskContext } from '../context.js';

export const definitionPane = (c: TaskContext): TemplateResult =>
  html`<ca-definition .definition=${c.detail.definition ?? null} memory="task-definition"></ca-definition>`;
