import { deriveRun, isPython, type JournalRow, type MonitorClient, type Plan, type TaskDefinition, type TaskOutcome } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../core/events.js';
import { factList } from '../../words/format.js';
import { factLine } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';

/** How long to wait before asking again for definitions that have not been recorded yet. */
const REFETCH_MS = 3000;

/**
 * What defines each kind of task in a run: a list of kinds, and the selected
 * one's definition. Fetches `/definitions` itself; while the run is live and a
 * kind has not recorded its definition yet, it asks again. A pick sends
 * `ca-navigate` {def}.
 *
 * @fires ca-navigate - `{def}`: another kind was selected
 */
@customElement('ca-definitions')
@localized()
export class CaDefinitions extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .defs { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 14px; align-items: start; }
      .deflist { display: flex; flex-direction: column; gap: 6px; }
      .defitem { padding: 9px 12px; border-radius: 10px; background: var(--panel); border: 1px solid var(--line); cursor: pointer;
        display: flex; flex-direction: column; gap: 2px; }
      .defitem:hover { border-color: var(--line2); }
      .defitem.sel { border-color: var(--accent); background: var(--accent-bg); }
      @media (max-width: 900px) {
        .defs { grid-template-columns: 1fr; }
      }
    `,
  ];

  @property({ attribute: false }) client!: MonitorClient;
  @property() run = '';
  /** The run is live: definitions may still appear. */
  @property({ type: Boolean }) live = false;
  /** The run's journal and plan: tasks and attempts per kind, and which kinds should have a definition. */
  @property({ attribute: false }) journal: JournalRow[] = [];
  @property({ attribute: false }) plan: Plan | null = null;
  /** The selected kind (null: the first with a plugin, else the first). */
  @property({ attribute: false }) selected: string | null = null;

  @state() private defs: TaskDefinition[] = [];
  private defsRun = '';
  private timer: ReturnType<typeof setTimeout> | null = null;

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.clearTimer();
    this.defsRun = '';
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.run && this.defsRun !== this.run) void this.load();
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    if ((changed.has('run') || changed.has('client')) && this.run && this.client && this.defsRun !== this.run) {
      this.defs = [];
      void this.load();
    }
  }

  protected override updated(): void {
    // A definition appears when the first task of its kind launches: ask again while the run is live and one is missing.
    const kinds = new Set(this.tasks().filter((t) => !isPython(t) && (t.tries.length || t.outcome === 'running')).map((t) => t.kind)).size;
    if (this.live && this.defsRun === this.run && this.defs.length < kinds && !this.timer) {
      this.timer = setTimeout(() => {
        this.timer = null;
        void this.load();
      }, REFETCH_MS);
    }
  }

  /** Every task of the run: the plan joined with the journal. */
  private tasks(): TaskOutcome[] {
    return [...deriveRun(this.journal, this.plan).outcomes.values()];
  }

  private clearTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private async load(): Promise<void> {
    if (!this.client || !this.run) return;
    const run = this.run;
    this.defsRun = run;
    let defs: TaskDefinition[] = [];
    try {
      defs = await this.client.definitions(run);
    } catch {
      defs = [];
    }
    if (run === this.run) this.defs = defs;
  }

  override render() {
    const defs = this.defs;
    // Python kinds record no definition: they are listed from the tasks so the list matches the tasks tab.
    const tasks = this.tasks();
    const pyKinds = [...new Set(tasks.filter((t) => isPython(t)).map((t) => t.kind))].filter((k) => !defs.some((d) => d.kind === k));
    if (!defs.length && !pyKinds.length) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${this.live ? msg('No definitions yet') : msg('No definitions')}</b></div>`;
    }
    const pySel = this.selected !== null && pyKinds.includes(this.selected) ? this.selected : null;
    const sel = pySel ? undefined : (defs.find((d) => d.kind === this.selected) ?? defs.find((d) => d.plugin) ?? defs[0]);
    const selKind = pySel ?? sel?.kind ?? pyKinds[0] ?? '';
    const counts = (k: string) => {
      const ts = tasks.filter((t) => t.kind === k);
      const n = ts.length;
      // A task refused before it started has a journal row but no attempt.
      const a = ts.reduce((x, t) => x + t.tries.length, 0);
      return factList(n === 1 ? msg('1 task') : msg(str`${n} tasks`), a === 1 ? msg('1 attempt') : msg(str`${a} attempts`));
    };
    return html`<div class="defs">
      <div class="deflist">
        ${repeat(
          defs,
          (d) => d.kind,
          (d) => html`<div class="defitem ${d.kind === selKind ? 'sel' : ''}" @click=${() => emit(this, 'ca-navigate', { def: d.kind })}>
            <b class="jmono">${d.kind}</b>
            <span class="meta words">${factLine([d.executor === 'python' ? 'Python' : d.role ? msg(str`Role ${d.role}`) : msg('No role'), ...counts(d.kind)])}</span>
          </div>`,
        )}
        ${repeat(
          pyKinds,
          (k) => k,
          (k) => html`<div class="defitem ${k === selKind ? 'sel' : ''}" @click=${() => emit(this, 'ca-navigate', { def: k })}>
            <b class="jmono">${k}</b>
            <span class="meta words">${factLine(['Python', ...counts(k)])}</span>
          </div>`,
        )}
      </div>
      <section class="panel">
        ${sel
          ? html`<h3 title=${msg('As recorded when its first task started (definitions/<kind>.json)')}>
                ${sel.kind}<span class="r">${sel.executor === 'python' ? msg('Python task') : sel.plugin ? msg(str`Plugin ${sel.name || ''}`) : msg('Defined in Python code')}</span>
              </h3>
              <ca-definition .definition=${sel} memory="definition:${sel.kind}"></ca-definition>`
          : html`<h3>${selKind}<span class="r">${msg('Python task')}</span></h3>
              <ca-definition .definition=${null}></ca-definition>`}
      </section>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-definitions': CaDefinitions;
  }
}
