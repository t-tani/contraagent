import { deriveRun, liveActivities, type JournalRow, type Plan, type Procs } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { keyed } from 'lit/directives/keyed.js';
import { starts } from '@contraagent/elements';
import { base } from '@contraagent/elements/styles';
import '@contraagent/elements/lanes/define';
import type { LanesStrings } from '@contraagent/elements/lanes';
import { laneStyles, lanesFromJournal } from '../../adapters/lanes.js';
import { getLocale } from '../../core/i18n.js';

/**
 * Every finished attempt as a bar as long as it took, on its kind's lane, the
 * running ones growing until now (the last six hours of the run), as
 * `<cae-lanes>` (`lanesFromJournal`).
 */
@customElement('ca-timeline')
@localized()
export class CaTimeline extends LitElement {
  static override styles = [base, css`:host { display: block; }`];

  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The run's plan: with the journal, why a task did not start, as the tasks list says it. Optional. */
  @property({ attribute: false }) plan: Plan | null = null;
  @property({ attribute: false }) procs: Procs | null = null;
  /** The run is live: its running tasks are drawn, growing every second. */
  @property({ type: Boolean }) live = false;
  /** The run drawn; the bars grow in when a run is first drawn, not on every update. */
  @property() run = '';

  override render() {
    const now = Date.now();
    const live = this.live
      ? liveActivities(this.procs).map((a) => ({ kind: a.kind, cls: a.cls, t0: starts.at(a.id, a.ageS, now) }))
      : [];
    const tl = lanesFromJournal(this.journal, live, deriveRun(this.journal, this.plan).outcomes, this.run);
    if (!tl)
      return html`<div class="blank" style="padding:28px"><span class="ic" aria-hidden="true">⏱</span>${this.live
        ? msg('No finished attempts yet')
        : msg('No finished attempts')}</div>`;
    const strings: Partial<LanesStrings> = {
      omitted: (n) => (n === 1 ? msg('1 older attempt not shown') : msg(str`${n} older attempts not shown`)),
    };
    return keyed(
      this.run,
      html`<cae-lanes .lanes=${tl.lanes} .barStyles=${laneStyles()} .omitted=${tl.omitted} ?live=${this.live}
        locale=${getLocale()} .strings=${strings}></cae-lanes>`,
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-timeline': CaTimeline;
  }
}
