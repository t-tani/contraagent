// A prompt and an instructions template as a reader reads them: the template's
// placeholders picked out, and a prompt's TELEMETRY line apart from its prose.
import { esc } from '@contraagent/elements';

/** `$unit` and `{{contract}}` picked out of an instructions template (escaped source). */
export function instructionsHtml(text: string): string {
  return markInstructions(esc(text));
}

/** The same, on already-rendered HTML. */
export const markInstructions = (html: string): string =>
  html
    .replace(/\$\{?([A-Za-z_]\w*)\}?/g, '<span class="pv">$&</span>')
    .replace(/\{\{contract\}\}/g, '<span class="pv pc">{{contract}}</span>');

/** A prompt's leading `TELEMETRY ...` line (which run and task it belongs to), apart from its prose. */
export function splitTelemetry(text: string): { head: string; body: string } {
  const m = text.match(/^(TELEMETRY [^\n]*)\n+([\s\S]*)$/);
  return m ? { head: m[1] ?? '', body: m[2] ?? '' } : { head: '', body: text };
}
