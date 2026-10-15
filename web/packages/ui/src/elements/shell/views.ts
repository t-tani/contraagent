// The view under the monitor's tabs: the element the view route's tab shows, given
// the data it reads.
import { hostOf, isRunLive, latestTask, runActivity, runRow, type MonitorClient, type MonitorSnapshot, type RunDerived } from '@contraagent/api';
import { msg } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import type { ViewRoute } from '../../core/view-route.js';
import { mixedReplay } from '../../words/run-line.js';
import '../overview/ca-overview.js';
import '../lists/ca-task-table.js';
import '../lists/ca-journal-table.js';
import '../lists/ca-contracts.js';
import '../lists/ca-definitions.js';
import '../lists/ca-procs-view.js';
import '../lists/ca-panel-view.js';
import '../task/ca-task-view.js';

export interface TabViewData {
  snap: MonitorSnapshot;
  viewRoute: ViewRoute;
  /** `deriveRun` of the run's journal and plan. */
  derived: RunDerived;
  /** The text filter, as typed. */
  q: string;
  client: MonitorClient;
  baseUrl: string;
}

/**
 * The view of `viewRoute.tab`; with no run, a blank page that says there are no
 * runs once the server's run list says so (the API's error is above it).
 */
export function tabView({ snap, viewRoute, derived, q, client, baseUrl }: TabViewData): TemplateResult {
  const { state } = snap;
  if (!viewRoute.run) {
    return html`<div class="blank">${snap.runsLoaded && !snap.error
      ? html`<span class="ic" aria-hidden="true">✦</span><b>${msg('No runs yet', { id: 'no-runs-yet' })}</b>`
      : nothing}</div>`;
  }
  const summary = runRow(snap.runs, snap.run);
  const live = isRunLive(state, summary);
  switch (viewRoute.tab) {
    case 'overview':
      return html`<ca-overview .state=${state} .summary=${summary} .host=${hostOf(snap.hosts?.hosts, summary)} .info=${snap.info} .run=${viewRoute.run} .layer=${viewRoute.layer} .unit=${viewRoute.unit} .sel=${viewRoute.sel}></ca-overview>`;
    case 'tasks':
      return html`<ca-task-table .run=${viewRoute.run} .journal=${state.journal} .plan=${state.plan} .kind=${viewRoute.kind} .q=${q} ?live=${live}></ca-task-table>`;
    case 'journal':
      return html`<ca-journal-table .run=${viewRoute.run} .rows=${state.journal} .plan=${state.plan} .fresh=${snap.fresh} .kind=${viewRoute.kind} .stop=${viewRoute.stop} .q=${q}
        .extras=${summary?.row_extras ?? []} ?replay-marks=${mixedReplay(summary)}></ca-journal-table>`;
    case 'outputs':
      return html`<ca-contracts .run=${viewRoute.run} .outputs=${state.outputs} .journal=${state.journal} .plan=${state.plan}></ca-contracts>`;
    case 'definitions':
      return html`<ca-definitions .client=${client} .run=${viewRoute.run} .journal=${state.journal} .plan=${state.plan} .live=${live}
        .selected=${viewRoute.def}></ca-definitions>`;
    case 'procs':
      return html`<ca-procs-view .procs=${state.procs} ?unresponsive=${runActivity(summary, !!state.procs?.alive) === 'unresponsive'}
        ?exported=${!!snap.info.export}></ca-procs-view>`;
    case 'stream':
      return html`<ca-task-view .client=${client} .journal=${state.journal} .plan=${state.plan} base-url=${baseUrl} .run=${viewRoute.run}
        .taskKey=${viewRoute.key ?? latestTask(derived.rows)} .view=${viewRoute.view} .round=${viewRoute.round} .live=${live}
        ?exported=${!!snap.info.export} ?replay-marks=${mixedReplay(summary)}></ca-task-view>`;
    default: {
      const name = viewRoute.tab.slice('panel:'.length);
      const info = snap.info.panels.find((p) => p.name === name);
      return html`<ca-panel-view .name=${name} .panel=${info} .data=${state.panels[name]}></ca-panel-view>`;
    }
  }
}
