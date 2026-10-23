// The landing page's replay: the demo pipeline's run, played again in the real
// elements. The flow's code appears line by line; then the run's plan, journal and
// transcripts are given to <ca-pipeline-graph>, <ca-kpis> and <ca-transcript> as
// they stood at each moment of the run, and the code lights the lines the running
// tasks were created on; the code's pane follows the line typed last, then the lines
// lit. One clock drives it all (requestAnimationFrame), and each frame is drawn from
// the replay's time alone. Where the window is decides when it starts, not how the
// scroll came there: on a wide screen once all of the window is on screen (where it
// stands flat, ./scene.css), on a narrow one when it reaches the upper half of the
// screen; it stops while it is off screen, and rests on the last frame. The list of
// the run's moments under the window lights each as it happens. The graph is only
// shown: no outline, open controls, zoom buttons or view switch. On a narrow screen
// the window shows one panel at a time, chosen by its tabs: the code while it
// appears, then the panel of each moment of the run as it comes (the graph, or the
// transcript of a correction), each for a while at least; once the reader picks a
// tab, that panel stays.
import type { FlowCallNode, JournalRow, Plan, PlanNode, TaskState } from '@contraagent/api';
import { adoptThemes } from '@contraagent/elements/themes';
import '@contraagent/ui/kpis';
import '@contraagent/ui/pipeline-graph';
import '@contraagent/ui/transcript';
import type { Timeline } from './timeline';

/** The run plays at this many times its own speed. */
const SPEED = 1.3;
/** Each line of code appears this long after the one before it (ms). */
const LINE_MS = 80;
/** The graph shows the plan as it stood when the run started, this long before the run plays (ms). */
const GRAPH_MS = 900;
/** The least replay time between two updates of the elements (ms). */
const FRAME_MS = 90;
/** The least replay time between two updates of the transcript (ms): a few new lines a second, as a log reads. */
const TRANSCRIPT_MS = 250;
/** After the reader scrolls the code's pane, it stays where they left it this long (ms). */
const READER_MS = 4000;
/** A panel the run's moments chose stays at least this long before the next moment's (ms). */
const DWELL_MS = 3200;
/** The panels a narrow screen shows one at a time (RunReplay.astro). */
type Panel = 'code' | 'graph' | 'transcript';
/** No journal rows: the same array each time, so the transcript is not drawn again for it. */
const NO_ROWS: JournalRow[] = [];

const epoch = (ts = ''): number => Date.parse(ts) / 1000;
const clock = (s: number): string => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

type Graph = HTMLElement & { plan: Plan; journal: JournalRow[]; run: string; live: boolean; controls: boolean };
type Kpis = HTMLElement & { plan: Plan; journal: JournalRow[] };
type Transcript = HTMLElement & { events: unknown[] | null; rows: JournalRow[]; live: boolean; run: string; updateComplete: Promise<boolean> };

/** A task's attempts as spans of the run (epoch seconds). */
interface Span { start: number; end: number; ok: boolean }

class Replay {
  private readonly root: HTMLElement;
  private readonly data: Timeline;
  private readonly lines: HTMLElement[];
  private readonly pre: HTMLElement;
  private readonly badges = new Map<number, HTMLElement>();
  private readonly graph: Graph;
  private readonly kpis: Kpis;
  private readonly transcript: Transcript;
  private readonly spotName: HTMLElement;
  private readonly status: HTMLElement;
  private readonly progress: HTMLElement;
  private readonly button: HTMLButtonElement;
  private readonly moments: HTMLElement[];
  private readonly spans = new Map<string, Span[]>();
  private readonly codeMs: number;
  private readonly runMs: number;
  private readonly tabs: HTMLButtonElement[];
  private readonly panes: HTMLElement[];
  /**
   * The panel of each part of the replay: when it comes (`at`, replay time in ms), and
   * when the tabs show it while they follow the run (`shown`: a panel stays a while
   * before the next), with the task whose transcript it shows (`spot`).
   */
  private readonly cues: { at: number; shown: number; panel: Panel; spot?: string }[];

  /** The replay's own time (ms), and the frame it was last advanced on. */
  private t = 0;
  private last: number | null = null;
  private raf = 0;
  private visible = false;
  private paused = false;
  /** What the graph and the numbers were last given, and at what replay time. */
  private pushed = '';
  private pushedAt = -Infinity;
  /** What the transcript was last given, at what replay time, and whether it is fading to another task's. */
  private tPushed = '';
  private tPushedAt = -Infinity;
  private tSpot = '';
  private switching = false;
  /** The lines the code's pane last followed, and when the reader last scrolled it. */
  private followed = '';
  private readerAt = -Infinity;
  /** The panel shown on a narrow screen, and whether the reader chose it (then the tabs no longer follow the run). */
  private panel: Panel = 'code';
  private chosen = false;
  private tabbed = false;

  constructor(root: HTMLElement, data: Timeline) {
    this.root = root;
    this.data = data;
    const q = <T extends HTMLElement>(s: string): T => root.querySelector<T>(s)!;
    this.lines = [...root.querySelectorAll<HTMLElement>('.rr-line')];
    this.pre = q('.rr-pre');
    const reader = (): void => void (this.readerAt = performance.now());
    for (const type of ['wheel', 'pointerdown', 'keydown', 'touchstart'] as const) this.pre.addEventListener(type, reader, { passive: true });
    for (const l of this.lines) {
      const b = l.querySelector<HTMLElement>('.rr-badge');
      if (b) this.badges.set(Number(l.dataset['n']), b);
    }
    this.graph = q('ca-pipeline-graph');
    this.kpis = q('ca-kpis');
    this.transcript = q('ca-transcript');
    this.spotName = q('.rr-spot-name');
    this.status = q('.rr-status');
    this.progress = q('.rr-progress-bar');
    this.button = q('.rr-toggle');
    this.moments = [...root.querySelectorAll<HTMLElement>('.rr-moment')];
    const created = new Map(data.plan.nodes.map((n) => [n.key, epoch(n.ts)]));
    for (const r of data.journal) {
      const end = epoch(r.ts);
      const list = this.spans.get(r.key) ?? [];
      // Times in the history are whole seconds: an attempt starts no earlier than its task was created.
      list.push({ start: Math.min(end, Math.max(end - (r.wall_s ?? 0), created.get(r.key) ?? -Infinity)), end, ok: r.ok });
      this.spans.set(r.key, list);
    }
    this.codeMs = this.lines.length * LINE_MS + 500;
    this.runMs = ((data.t1 - data.t0) * 1000) / SPEED;
    this.graph.run = data.run;
    this.graph.controls = false;
    this.transcript.run = data.run;
    this.button.addEventListener('click', () => this.toggle());

    this.tabs = [...root.querySelectorAll<HTMLButtonElement>('.rr-tabs [role="tab"]')];
    this.panes = [...root.querySelectorAll<HTMLElement>('.rr-pane[data-panel]')];
    const runAt = (at: number): number => this.codeMs + GRAPH_MS + (at * 1000) / SPEED;
    this.cues = [
      { at: 0, shown: 0, panel: 'code' },
      { at: this.codeMs, shown: this.codeMs, panel: 'graph' },
    ];
    for (const m of data.moments) {
      const at = runAt(m.at);
      const shown = Math.min(this.total, Math.max(at, this.cues.at(-1)!.shown + DWELL_MS));
      this.cues.push({ at, shown, panel: m.shows, spot: m.spot });
    }
    for (const tab of this.tabs) {
      tab.addEventListener('click', () => this.choose(tab.dataset['panel'] as Panel));
      tab.addEventListener('keydown', (e) => {
        const i = this.tabs.indexOf(tab);
        const n = this.tabs.length;
        const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i + n - 1) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
        if (to < 0) return;
        e.preventDefault();
        this.tabs[to].focus();
        this.choose(this.tabs[to].dataset['panel'] as Panel);
      });
    }
    const narrow = matchMedia('(max-width: 49.99rem)');
    this.setTabbed(narrow.matches);
    narrow.addEventListener('change', () => this.setTabbed(narrow.matches));
  }

  /**
   * The tabs on a narrow screen, or every panel at once on a wide one: the roles of a
   * tab list are on the panels only while there are tabs.
   */
  private setTabbed(on: boolean): void {
    this.tabbed = on;
    this.root.classList.toggle('rr-tabbed', on);
    for (const p of this.panes) {
      if (on) {
        p.setAttribute('role', 'tabpanel');
        p.setAttribute('aria-labelledby', `rr-tab-${p.dataset['panel']}`);
      } else {
        p.removeAttribute('role');
        p.removeAttribute('aria-labelledby');
      }
    }
    // The numbers scroll sideways in one row: a region the keyboard reaches.
    const strip = this.kpis.parentElement!;
    if (on) {
      strip.setAttribute('role', 'region');
      strip.setAttribute('aria-label', 'The run in numbers');
      strip.tabIndex = 0;
    } else {
      strip.removeAttribute('role');
      strip.removeAttribute('aria-label');
      strip.removeAttribute('tabindex');
    }
    this.show(this.panel);
  }

  /** The reader's tab: its panel stays. The graph or the transcript before the run plays starts the run at once. */
  private choose(panel: Panel): void {
    this.chosen = true;
    if (panel !== 'code' && this.t < this.codeMs) {
      this.t = this.codeMs;
      this.draw(true);
    }
    this.show(panel);
  }

  private show(panel: Panel): void {
    this.panel = panel;
    for (const tab of this.tabs) {
      const on = tab.dataset['panel'] === panel;
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
    }
    for (const p of this.panes) p.classList.toggle('rr-shown', p.dataset['panel'] === panel);
  }

  private get total(): number {
    return this.codeMs + GRAPH_MS + this.runMs;
  }

  /** The run's time (epoch seconds) at the replay's time; before the run plays, just before its start. */
  private sim(t: number): number {
    const into = t - this.codeMs - GRAPH_MS;
    return into < 0 ? this.data.t0 - 0.001 : this.data.t0 + (Math.min(into, this.runMs) * SPEED) / 1000;
  }

  /** The first frame, before the replay starts. */
  prime(): void {
    this.draw(true);
  }

  start(): void {
    this.root.classList.add('rr-playing');
    this.visible = true;
    this.loop();
  }

  setVisible(on: boolean): void {
    this.visible = on;
    if (on) this.loop();
  }

  /** The last frame at once: what the replay shows with reduced motion. */
  finish(): void {
    this.t = this.total;
    this.draw(true);
    this.root.classList.add('rr-ended');
  }

  private toggle(): void {
    if (this.t >= this.total) {
      this.t = 0;
      this.pushed = '';
      this.pushedAt = -Infinity;
      this.tPushed = '';
      this.tPushedAt = -Infinity;
      this.followed = '';
      this.chosen = false;
      this.root.classList.remove('rr-ended');
      this.paused = false;
    } else this.paused = !this.paused;
    this.label();
    this.loop();
  }

  private label(): void {
    const ended = this.t >= this.total;
    this.button.textContent = ended ? 'Replay' : this.paused ? 'Play' : 'Pause';
    this.button.dataset['state'] = ended ? 'ended' : this.paused ? 'paused' : 'playing';
    this.root.classList.toggle('rr-paused', this.paused && !ended);
  }

  private loop(): void {
    if (this.raf || !this.visible || this.paused || this.t >= this.total) return;
    this.last = null;
    const tick = (now: number): void => {
      this.raf = 0;
      if (!this.visible || this.paused) return;
      if (this.last !== null) this.t = Math.min(this.total, this.t + Math.min(100, now - this.last));
      this.last = now;
      this.draw(false);
      if (this.t >= this.total) {
        this.root.classList.add('rr-ended');
        this.label();
        return;
      }
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private stateAt(key: string, s: number): TaskState {
    const spans = this.spans.get(key) ?? [];
    if (spans.some((x) => x.end <= s && x.ok)) return 'done';
    if (spans.some((x) => x.start <= s && s < x.end)) return 'running';
    if (spans.length && spans.every((x) => x.end <= s)) return 'failed';
    return 'pending';
  }

  /** The plan as it stood at `s`: the tasks created by then, each in its state then. */
  private planAt(s: number): Plan {
    const created = Math.max(s, this.data.t0);
    const nodes: PlanNode[] = this.data.plan.nodes
      .filter((n) => epoch(n.ts) <= created)
      .map((n) => {
        const state = this.stateAt(n.key, s);
        if (state === n.state) return n;
        const running = this.spans.get(n.key)?.find((x) => x.start <= s && s < x.end);
        return { ...n, state, stop: '', attempts: running ? 1 : 0, wall_s: running ? s - running.start : 0 };
      });
    const groups = (this.data.plan.groups ?? []).map((g) => {
      const mine = nodes.filter((n) => n.group === g.id);
      const count = (st: TaskState): number => mine.filter((n) => n.state === st).length;
      return { ...g, total: mine.length, done: count('done'), running: count('running'), pending: count('pending'), failed: count('failed') };
    });
    const flowCalls = (this.data.plan.flow_calls ?? []).map((f): FlowCallNode => {
      const own = this.data.plan.nodes.filter((n) => n.flow_call === f.id || (n.flow_call ?? '').startsWith(`${f.id}.`));
      const over = own.length > 0 && own.every((n) => this.stateAt(n.key, s) === 'done');
      return over ? f : { ...f, state: 'running' };
    });
    return { ...this.data.plan, nodes, groups, flow_calls: flowCalls };
  }

  private draw(force: boolean): void {
    const t = this.t;
    const s = this.sim(t);
    const ended = t >= this.total;
    const shown = Math.min(this.lines.length, Math.floor(t / LINE_MS) + 1);
    this.lines.forEach((l, i) => l.classList.toggle('rr-on', i < shown));
    this.root.classList.toggle('rr-graph-on', t >= this.codeMs);
    this.progress.style.transform = `scaleX(${(t / this.total).toFixed(4)})`;

    const plan = this.planAt(s);
    const journal = this.data.journal.filter((r) => epoch(r.ts) <= s);
    const running = plan.nodes.filter((n) => n.state === 'running');
    const done = plan.nodes.filter((n) => n.state === 'done').length;

    // The lines of code the running tasks were created on, and how many on each.
    const counts = new Map<number, number>();
    for (const n of running) {
      const line = n.flow?.at(-1)?.line ?? 0;
      counts.set(line, (counts.get(line) ?? 0) + 1);
    }
    for (const l of this.lines) {
      const n = Number(l.dataset['n']);
      const c = counts.get(n) ?? 0;
      l.classList.toggle('rr-live', c > 0);
      const b = this.badges.get(n);
      if (b) b.textContent = c ? `${c} running` : '';
    }
    this.follow(shown, counts);

    const into = s - this.data.t0;
    const phase = t < this.codeMs + GRAPH_MS ? 'not started' : ended ? 'finished' : 'running';
    this.status.lastElementChild!.textContent = `${phase} | ${done} of ${plan.nodes.length} done | ${clock(Math.max(0, into))}`;
    this.root.dataset['phase'] = phase;

    for (const m of this.moments) {
      const at = Number(m.dataset['at']);
      m.classList.toggle('rr-past', into >= at && phase !== 'not started');
    }
    const past = this.moments.filter((m) => m.classList.contains('rr-past'));
    for (const m of this.moments) m.classList.toggle('rr-now', m === past.at(-1));

    // A narrow screen: the panel of the part of the run the tabs follow, until the reader picks a tab.
    const following = this.tabbed && !this.chosen;
    const cue = this.cues.findLast((c) => c.shown <= t) ?? this.cues[0];
    if (following && cue.panel !== this.panel) this.show(cue.panel);

    // Once a task's correction round has started, its transcript, until the next one's.
    const newest = (at: (x: Timeline['spots'][number]) => number) =>
      this.data.spots.filter((x) => at(x) <= s).reduce<Timeline['spots'][number] | undefined>((a, b) => (a && at(a) >= at(b) ? a : b), undefined);
    // While the tabs follow the run, the transcript of the correction its panel is for (the panel may come later than the run).
    const named = following ? this.data.spots.find((x) => x.key === cue.spot) : undefined;
    const spot = named ?? newest((x) => x.corrected) ?? newest((x) => x.from) ?? this.data.spots[0];
    const started = s >= this.data.t0;
    // A prefix of the same events: the transcript appends the new ones (ca-transcript).
    const upTo = started ? spot.times.findIndex((at) => at > s) : 0;
    const events = spot.events.slice(0, upTo < 0 ? spot.events.length : upTo);
    const live = started && s < spot.to;
    this.feedTranscript(spot, events, live, force || t >= this.total);

    const key = `${plan.nodes.map((n) => n.state[0]).join('')}|${journal.length}|${ended}`;
    if (key === this.pushed || (!force && !ended && t - this.pushedAt < FRAME_MS)) return;
    this.pushed = key;
    this.pushedAt = t;
    this.graph.live = !ended;
    this.graph.plan = plan;
    this.graph.journal = journal;
    this.kpis.plan = plan;
    this.kpis.journal = journal;
  }

  /**
   * The code's pane, where it scrolls (a short window): while the code appears, the
   * line typed last stays in view; while the run plays, the lines lit, centred when
   * they are out of view. Smoothly, unless the reader asks for reduced motion; not
   * while the reader scrolls it.
   */
  private follow(shown: number, counts: Map<number, number>): void {
    const lit = shown < this.lines.length ? [this.lines[shown - 1]] : this.lines.filter((l) => counts.has(Number(l.dataset['n'])));
    const key = lit.map((l) => l.dataset['n']).join(',');
    if (!lit.length || key === this.followed) return;
    this.followed = key;
    const pre = this.pre;
    if (pre.scrollHeight <= pre.clientHeight + 1 || performance.now() - this.readerAt < READER_MS) return;
    const first = lit[0];
    const last = lit.at(-1)!;
    const top = first.offsetTop;
    const bottom = last.offsetTop + last.offsetHeight;
    const pad = first.offsetHeight * 1.5;
    const view = pre.clientHeight;
    if (top >= pre.scrollTop + pad && bottom <= pre.scrollTop + view - pad) return;
    // Typing: the new line near the foot of the pane; the run: the lit lines in its middle.
    const to = shown < this.lines.length ? bottom - view + pad : bottom - top > view - 2 * pad ? top - pad : (top + bottom - view) / 2;
    const behavior = matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    pre.scrollTo({ top: Math.max(0, Math.round(to)), behavior });
  }

  /**
   * The transcript, at most every TRANSCRIPT_MS: the new events of the same task appended;
   * another task's transcript after the panel faded out, then in again (once per task).
   */
  private feedTranscript(spot: Timeline['spots'][number], events: Timeline['spots'][number]['events'], live: boolean, atOnce: boolean): void {
    const key = `${spot.key}:${events.length}|${live}`;
    if (key === this.tPushed || this.switching) return;
    const other = this.tSpot !== '' && spot.key !== this.tSpot;
    if (!atOnce && !other && this.t - this.tPushedAt < TRANSCRIPT_MS) return;
    this.tPushed = key;
    this.tPushedAt = this.t;
    const give = (): void => {
      this.tSpot = spot.key;
      this.spotName.textContent = spot.name;
      this.transcript.live = live;
      this.transcript.rows = live ? NO_ROWS : spot.rows;
      this.transcript.events = events;
    };
    const body = this.transcript.parentElement;
    if (!other || atOnce || !body || matchMedia('(prefers-reduced-motion: reduce)').matches) return give();
    this.switching = true;
    body.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, easing: 'ease-in', fill: 'forwards' }).onfinish = () => {
      give();
      void this.transcript.updateComplete.then(() => {
        body.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: 'ease-out', fill: 'forwards' });
        this.switching = false;
      });
    };
  }
}

/** The themes' rules in the page, and the replay's theme following the site's. */
function themes(root: HTMLElement): void {
  adoptThemes(document);
  const html = document.documentElement;
  const set = (): void => root.setAttribute('data-ca-theme', html.dataset['theme'] === 'light' ? 'contraagent-light' : 'contraagent-dark');
  set();
  new MutationObserver(set).observe(html, { attributes: true, attributeFilter: ['data-theme'] });
}

for (const root of document.querySelectorAll<HTMLElement>('[data-run-replay]')) {
  const data = JSON.parse(root.querySelector('script[type="application/json"]')!.textContent) as Timeline;
  themes(root);
  const replay = new Replay(root, data);
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) replay.finish();
  else {
    replay.prime();
    let started = false;
    let inView = false;
    const show = (): void => replay.setVisible(inView && !document.hidden);
    const begin = (): void => {
      if (started) return;
      started = true;
      replay.start();
    };
    const wide = matchMedia('(min-width: 50rem)');
    new IntersectionObserver(
      ([e]) => {
        if (!e) return;
        inView = e.isIntersecting;
        if (inView && !started && !wide.matches) begin();
        else if (started) show();
      },
      { rootMargin: '0px 0px -45% 0px' },
    ).observe(root);
    // A wide screen: the window is no taller than the screen, and the replay starts once all of it is on it.
    new IntersectionObserver(
      ([e]) => {
        if (!e?.isIntersecting || !wide.matches) return;
        const whole = Math.min(e.boundingClientRect.height, e.rootBounds?.height ?? innerHeight);
        // On screen as a whole, or scrolled past its top.
        if (e.intersectionRect.height >= whole * 0.97 || e.boundingClientRect.top < 0) begin();
      },
      { threshold: [0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.97, 0.99, 1] },
    ).observe(root.querySelector('.rr-window')!);
    document.addEventListener('visibilitychange', () => started && show());
  }
}
