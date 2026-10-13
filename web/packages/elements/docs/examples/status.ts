// Statuses, a legend and a row of facts, drawn by the primitives into an element
// of your own: its styles start from `base` (the tokens and the status rules),
// plus `legendStyles` for the legend.
import { base, factLine, legend, legendStyles, pill, statusWord } from '@contraagent/elements';
import { LitElement, html } from 'lit';

class BuildSummary extends LitElement {
  static override styles = [base, legendStyles];

  override render() {
    return html`<p>
        ${pill({ text: 'passed', tone: 'done' })} ${pill({ text: 'failed', tone: 'failed', title: 'exit code 2' })}
        ${pill({ text: 'running', tone: 'running' })} ${statusWord({ text: 'queued', tone: 'attention' })}
      </p>
      <p class="meta words">${factLine(['12 jobs', { text: '1 failed', tone: 'failed' }, '4m 05s'])}</p>
      ${legend(
        [
          { label: 'passed', tone: 'done', shape: 'round' },
          { label: 'failed', tone: 'failed', shape: 'square' },
          { label: 'queued', tone: 'attention', shape: 'ring' },
        ],
        { label: 'Job states' },
      )}`;
  }
}

export function mount(host: HTMLElement): void {
  if (!customElements.get('build-summary')) customElements.define('build-summary', BuildSummary);
  host.replaceChildren(document.createElement('build-summary'));
}
