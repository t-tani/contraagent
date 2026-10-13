// A prompt as a reader reads it: markdown with a rendered/source switch, and its
// leading TELEMETRY line (which run and task it belongs to) apart, so the prose
// reads as prose.
import { msg } from '@lit/localize';
import { html, type TemplateResult } from 'lit';
import '@contraagent/elements/markdown/define';
import { splitTelemetry } from '../../words/prompt.js';

/** `text` in a `<cae-markdown>`, in the reader's language. Call it from a `@localized()` element's render. */
export function promptText(text: string): TemplateResult {
  const strings = { showRendered: msg('Show rendered'), showSource: msg('Show source') };
  return html`<cae-markdown .text=${text} .split=${splitTelemetry} .strings=${strings}></cae-markdown>`;
}
