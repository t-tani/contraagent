import { elapsedS, result, runActivity, type HostSummary, type Plan, type Procs, type RunSummary } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { starts } from '@contraagent/elements';
import { facts, fmtDur, localTime, sentence } from '../../words/format.js';
import { hostFact, lastReport, noReportLabel } from '../../words/hosts.js';
import { preflightLabel, preflightStoppedCause, preflightStoppedTitle, preflightTip } from '../../words/preflight.js';
import { preflightRows } from '../../adapters/preflight.js';
import { toneAttr, type Tone } from '@contraagent/elements';
import { base, factStyles } from '@contraagent/elements/styles';
import '@contraagent/elements/count/define';

/** The mark of how a run ended (■ for a run with no tasks). */
const MARK: Record<Tone, string> = { failed: '✕', attention: '◌', done: '✓', running: '', muted: '■', neutral: '■' };

/**
 * The run's own process: running (pid, run group, how many tasks at once,
 * command line), or not running, and then how it finished: with errors, or with
 * tasks not done (from `plan`). On a hub, a run whose host stopped reporting
 * (`summary.unresponsive`) is neither: no report from its host, since `host.last_seen`.
 * Under it, the models the run's preflight found available, replaced or not
 * available (`plan.preflight`); a run its preflight ended names the kinds that did it.
 */
@customElement('ca-run-driver')
@localized()
export class CaRunDriver extends LitElement {
  static override styles = [
    base,
    factStyles,
    css`
      :host { display: block; }
      .drv { display: flex; gap: 14px; align-items: flex-start; }
      .drv-ic { width: 42px; height: 42px; border-radius: 12px; flex: none; display: grid; place-items: center; font-size: 16px;
        background: var(--raise); color: var(--text-muted); }
      .drv.on .drv-ic { background: var(--status-running-bg); box-shadow: 0 0 0 1px color-mix(in srgb, var(--status-running) 35%, transparent), 0 0 22px var(--status-running-bg); }
      /* how a run ended: the mark's shape and the title's words carry it; the colour only where a status applies */
      .drv-ic[data-tone] { color: var(--tone); font-weight: 700; }
      .drv-ic[data-tone='failed'], .drv-ic[data-tone='attention'] { background: var(--tone-bg); }
      .drv.on .drv-ic .spin { width: 18px; height: 18px; }
      .drv-t { font-size: 15px; font-weight: 600; }
      .drv-up { font-family: var(--mono); font-size: 12px; color: var(--status-running); margin-left: 6px; font-weight: 400; }
      .drv-cmd { margin-top: 8px; }
      .drv-cmd summary { cursor: pointer; font-size: 11px; color: var(--text-muted); }
      .pf { margin-top: 10px; font-size: 12px; }
      .pf-h { color: var(--text-muted); font-size: 11px; margin-bottom: 4px; }
      /* a label, then its fact: one row each, the facts in one column */
      .pf-rows { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 3px 12px; margin: 0; }
      .pf-rows dt { color: var(--text-muted); }
      .pf-rows dt[data-tone] { color: var(--tone); }
      .pf-rows dd { margin: 0; color: var(--text-2); overflow-wrap: anywhere; }
      .drv-cmd code { display: block; margin-top: 4px; white-space: pre-wrap; word-break: break-all; color: var(--text-2); max-height: 120px; overflow: auto; }
    `,
  ];

  @property({ attribute: false }) procs: Procs | null = null;
  @property({ attribute: false }) summary: RunSummary | undefined;
  @property({ attribute: false }) plan: Plan = { nodes: [], groups: [] };
  /** The run's host (a hub): when it last reported. */
  @property({ attribute: false }) host: HostSummary | undefined;

  /**
   * How a run that is not running ended, as its title: everything scheduled ran
   * (finished), with or without failed or not-started tasks, or some tasks never got their turn (stopped).
   */
  private stateTitle(): [text: string, tone: Tone] {
    if (this.plan.preflight?.stopped?.length) return [preflightStoppedTitle(), 'failed'];
    if (!this.plan.nodes.length) return [msg('Not running'), 'neutral'];
    const r = result(this.plan);
    if (r.failed) return [r.failed === 1 ? msg('Finished with 1 task failed') : msg(str`Finished with ${r.failed} tasks failed`), 'failed'];
    if (r.left) return [r.left === 1 ? msg('Finished with 1 task not done') : msg(str`Finished with ${r.left} tasks not done`), 'attention'];
    if (r.notStarted) return [r.notStarted === 1 ? msg('Finished with 1 task not started') : msg(str`Finished with ${r.notStarted} tasks not started`), 'attention'];
    return [msg('Finished'), 'done'];
  }

  override render() {
    const p = this.procs;
    const r = this.summary;
    if (!p?.alive) {
      // Its host stopped reporting (a hub): not known to run, not known to have ended.
      const quiet = runActivity(r) === 'unresponsive';
      const [title, tone]: [string, Tone] = quiet ? [sentence(noReportLabel()), 'attention'] : this.stateTitle();
      const took = quiet ? null : elapsedS(r);
      return html`<div class="drv off">
        <div class="drv-ic" data-tone=${toneAttr(tone)} aria-hidden="true">${MARK[tone]}</div>
        <div>
          <div class="drv-t tone-text" data-tone=${tone === 'done' ? nothing : toneAttr(tone)}>${title}</div>
          <div class="meta">${facts(
            this.plan.preflight?.stopped?.length ? preflightStoppedCause(this.plan.preflight.stopped) : '',
            quiet ? lastReport(this.host) : '',
            !r?.last_ts ? msg('No activity') : quiet ? msg(str`Last activity ${localTime(r.last_ts, true)}`) : msg(str`Ended ${localTime(r.last_ts, true)}`),
            took == null ? '' : msg(str`Took ${fmtDur(took)}`),
            r?.run_group ? msg(str`Run group ${r.run_group}`) : '',
            quiet ? hostFact(r?.host_id ?? '') : '',
          )}</div>
          ${this.preflight()}
        </div>
      </div>`;
    }
    const started = Date.parse(p.started_at);
    const since = starts.at(`drv:${p.pid ?? ''}`, Number.isNaN(started) ? 1 : (Date.now() - started) / 1000);
    const rows: [string, string | number][] = [
      [msg('PID'), p.pid ?? '—'],
      [msg('Run group'), p.run_group],
      [msg('Running at once (limit)'), p.max_workers || '—'],
      [msg('Started'), localTime(p.started_at, true)],
    ];
    return html`<div class="drv on">
      <div class="drv-ic"><span class="spin"></span></div>
      <div style="min-width:0">
        <div class="drv-t">${msg('Running')} <cae-elapsed class="drv-up" .since=${since}></cae-elapsed></div>
        <div class="drv-facts">${rows.map(([k, v]) => html`<span><i>${k}</i>${v}</span>`)}</div>
        ${this.preflight()}
        <details class="drv-cmd"><summary>${msg('Command line')}</summary><code>${p.argv.join(' ')}</code></details>
      </div>
    </div>`;
  }

  /** The preflight's rows under their label; nothing for a run with no preflight. */
  private preflight() {
    const pf = this.plan.preflight;
    const rows = preflightRows(pf);
    if (!pf || !rows.length) return nothing;
    return html`<div class="pf">
      <div class="pf-h" title=${preflightTip(pf.policy)}>${preflightLabel()}</div>
      <dl class="pf-rows">
        ${rows.map(
          (r) => html`<dt data-tone=${toneAttr(r.tone)} title=${r.tip || nothing}>${r.label}</dt><dd class="jmono">${r.text}</dd>`,
        )}
      </dl>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-run-driver': CaRunDriver;
  }
}

