// Who ran a transcript: chips for the coding agent (the CLI), the model and the role.
import { msg } from '@lit/localize';
import { css, html, nothing, type TemplateResult } from 'lit';
import type { Who } from './transcript-model.js';

export function whoChips(w: Who | null | undefined): TemplateResult {
  if (!w) return html``;
  return html`${w.agent
    ? html`<span class="who agent" title=${msg('The CLI that ran the task (claude, omp)')}
        ><span class="who-l">${msg('coding agent')}</span>${w.agent}</span
      >`
    : nothing}${w.model
    ? html`<span class="who model" title=${msg('The language model the coding agent used')}
        ><span class="who-l">${msg('model')}</span>${w.model}</span
      >`
    : nothing}${w.role
    ? html`<span class="who role" title=${msg('The agent definition the coding agent ran as (agents/<role>.md)')}
        ><span class="who-l">${msg('role')}</span>${w.role}</span
      >`
    : nothing}`;
}

export const whoStyles = css`
  .who { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600; padding: 2px 9px;
    border-radius: 7px; border: 1px solid var(--line2); white-space: nowrap; }
  .who-l { font-size: 10px; font-weight: 400; opacity: 0.75; font-family: var(--sans); }
  .who.agent { color: var(--live); border-color: rgba(34, 211, 238, 0.4); background: var(--live-a); }
  .who.model { color: var(--llm); border-color: rgba(167, 139, 250, 0.45); background: var(--llm-a); font-family: var(--mono); }
  .who.role { color: var(--fg2); font-family: var(--mono); font-weight: 500; }
`;
