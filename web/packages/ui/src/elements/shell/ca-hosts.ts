import type { Hosts, HostSummary } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { statusWord } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';
import { fmtDur, localTime } from '../../words/format.js';
import { hostStateLabel, hostsLine, noReportCount, runCount } from '../../words/hosts.js';
import '../overview/ca-quota.js';

/** The column of a host's runs, counted. */
const runsLabel = () => msg('Runs', { id: 'col-runs', desc: "A column: a host's runs, counted" });

/**
 * The hosts behind a hub's runs (`/api/hosts`): each host's state, its last
 * report, the seconds between its reports and its runs; then each account's
 * utilization over every run of every host, as the overview shows a run's.
 */
@customElement('ca-hosts')
@localized()
export class CaHosts extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .g12 { align-content: start; }
      table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
      th, td { text-align: start; padding: 8px 10px; border-top: 1px solid var(--line); vertical-align: baseline; }
      thead th { border-top: 0; font-size: 11.5px; font-weight: 600; color: var(--text-muted); white-space: nowrap; }
      tbody th { font-family: var(--mono); font-weight: 600; color: var(--text); overflow-wrap: anywhere; }
      .num { font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
      td.runs { color: var(--text-2); }
      /* Narrow: one block per host, each value under its column's name. */
      @media (max-width: 640px) {
        thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
        tr { display: block; padding: 8px 0; border-top: 1px solid var(--line); }
        tbody tr:first-child { border-top: 0; }
        th, td { display: flex; gap: 12px; padding: 2px 0; border: 0; white-space: normal; }
        td::before { content: attr(data-label); flex: 0 0 9em; color: var(--text-muted); font-family: var(--sans); font-size: 11.5px; }
      }
    `,
  ];

  /** The host list (`/api/hosts`); null until it arrives. */
  @property({ attribute: false }) hosts: Hosts | null = null;

  private row(h: HostSummary) {
    const quiet = !h.up;
    return html`<tr>
      <th scope="row">${h.host_id}</th>
      <td data-label=${msg('Status')}>${statusWord({ text: hostStateLabel(h), tone: quiet ? 'attention' : 'done' })}</td>
      <td data-label=${msg('Last report')} class="num" title=${h.last_seen}>${localTime(h.last_seen, true) || '—'}</td>
      <td data-label=${msg('Report interval')} class="num">${h.interval_s == null ? '—' : fmtDur(h.interval_s)}</td>
      <td data-label=${runsLabel()} class="runs"
        ><span>${runCount(h.runs)}${h.running ? html` | ${msg(str`${h.running} running`)}` : nothing}${h.unresponsive
          ? html` | <span class="tone-text" data-tone="attention">${noReportCount(h.unresponsive)}</span>`
          : nothing}</span></td
      >
    </tr>`;
  }

  override render() {
    const hosts = this.hosts?.hosts ?? [];
    const quota = this.hosts?.quota ?? [];
    return html`<div class="g12">
      <section class="panel c12 enter">
        <h3>${msg('Hosts')}<span class="r">${hostsLine(hosts)}</span></h3>
        ${hosts.length
          ? html`<table>
              <thead><tr>
                <th scope="col">${msg('Host')}</th><th scope="col">${msg('Status')}</th><th scope="col">${msg('Last report')}</th>
                <th scope="col">${msg('Report interval')}</th><th scope="col">${runsLabel()}</th>
              </tr></thead>
              <tbody>${hosts.map((h) => this.row(h))}</tbody>
            </table>`
          : html`<div class="meta">${msg('No hosts')}</div>`}
      </section>
      ${quota.length
        ? html`<section class="panel c12 enter">
            <h3 title=${msg('Reported at each agent session start. Account-wide: every task that runs at once shares it.')}>
              ${msg('Subscription usage')}<span class="r">${msg('Per account, first → last reading')}</span></h3>
            <ca-quota .accounts=${quota}></ca-quota>
          </section>`
        : nothing}
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-hosts': CaHosts;
  }
}
