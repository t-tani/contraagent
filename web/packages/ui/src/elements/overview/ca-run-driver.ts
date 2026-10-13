import { elapsedS, result, type Plan, type Procs, type RunSummary } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { starts } from '@contraagent/elements';
import { facts, fmtDur, localTime } from '../../words/format.js';
import { toneAttr, type Tone } from '@contraagent/elements';
import { base, factStyles } from '@contraagent/elements/styles';
import '@contraagent/elements/count/define';

/** The mark of how a run ended (■ for a run with no tasks). */
const MARK: Record<Tone, string> = { failed: '✕', attention: '◌', done: '✓', running: '', muted: '■', neutral: '■' };

/**
 * The run's own process: running (pid, run group, how many tasks at once,
 * command line), or not running, and then how it finished: with errors, or with
 * tasks not done (from `plan`).
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
      .drv-cmd code { display: block; margin-top: 4px; white-space: pre-wrap; word-break: break-all; color: var(--text-2); max-height: 120px; overflow: auto; }
    `,
  ];

  @property({ attribute: false }) procs: Procs | null = null;
  @property({ attribute: false }) summary: RunSummary | undefined;
  @property({ attribute: false }) plan: Plan = { nodes: [], groups: [] };

  /**
   * How a run that is not running ended, as its title: everything scheduled ran
   * (finished), with or without errors, or some tasks never got their turn (stopped).
   */
  private stateTitle(): [text: string, tone: Tone] {
    if (!this.plan.nodes.length) return [msg('Not running'), 'neutral'];
    const r = result(this.plan);
    if (r.failed) return [msg('Finished with errors'), 'failed'];
    if (r.left) return [r.left === 1 ? msg('Finished with 1 task not done') : msg(str`Finished with ${r.left} tasks not done`), 'attention'];
    if (r.notStarted) return [msg('Finished with errors'), 'attention'];
    return [msg('Finished'), 'done'];
  }

  override render() {
    const p = this.procs;
    const r = this.summary;
    if (!p?.alive) {
      const [title, tone] = this.stateTitle();
      const took = elapsedS(r);
      return html`<div class="drv off">
        <div class="drv-ic" data-tone=${toneAttr(tone)} aria-hidden="true">${MARK[tone]}</div>
        <div>
          <div class="drv-t tone-text" data-tone=${tone === 'done' ? nothing : toneAttr(tone)}>${title}</div>
          <div class="meta">${facts(
            r?.last_ts ? msg(str`Ended ${localTime(r.last_ts, true)}`) : msg('No activity'),
            took == null ? '' : msg(str`Took ${fmtDur(took)}`),
            r?.run_group ? msg(str`Run group ${r.run_group}`) : '',
          )}</div>
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
        <details class="drv-cmd"><summary>${msg('Command line')}</summary><code>${p.argv.join(' ')}</code></details>
      </div>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-run-driver': CaRunDriver;
  }
}

