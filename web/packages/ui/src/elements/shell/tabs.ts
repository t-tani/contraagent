// The monitor's tab list: the built-in views, then the custom views; each tab
// with its count, and a line under the selected one. The selected tab is bold
// and underlined, not only coloured. A list wider than its room scrolls
// sideways, with a shade at each edge that has more tabs past it. What a view
// filters by stands at the end of the line.
import { isRunPanel, type Info } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { css, html, nothing, type TemplateResult } from 'lit';
import { toneAttr } from '@contraagent/elements';
import type { Tab } from '../../core/view-route.js';
import type { Tone } from '../../lib/tone.js';

export interface TabInfo {
  id: Tab;
  label: string;
  /** A custom view's own mark (`icon` of its panel), shown on its heading. */
  icon: string;
  tip?: string;
  panel: boolean;
}

/** The built-in tabs, in the current locale (call at render time). */
const builtinTabs = (): Omit<TabInfo, 'panel' | 'icon'>[] => [
  { id: 'overview', label: msg('Overview') },
  { id: 'tasks', label: msg('Tasks', { id: 'tab-tasks', desc: 'Tab: the list of tasks' }) },
  { id: 'journal', label: msg('History'), tip: 'journal.jsonl' },
  { id: 'outputs', label: msg('Outputs') },
  { id: 'definitions', label: msg('Definitions') },
  { id: 'procs', label: msg('Processes') },
  { id: 'stream', label: msg('Task detail') },
];

/** Every tab, in the current locale: the built-in ones, then one per custom view computed per run (`panels`; a trends panel is not a run's tab). */
export function monitorTabs(panels: Info['panels']): TabInfo[] {
  return [
    ...builtinTabs().map((t) => ({ ...t, icon: '', panel: false })),
    ...panels.filter(isRunPanel).map((p) => ({
      id: `panel:${p.name}` as Tab,
      label: p.title || p.name,
      icon: p.icon || '',
      tip: p.description ? msg(str`${p.description} (custom view)`) : msg('Custom view'),
      panel: true,
    })),
  ];
}

/** The id of tab `i` in the tab list, which the view below it (`role="tabpanel"`) names as its label. */
export const tabId = (i: number): string => `tab-${i}`;

/**
 * The tab list: `current` selected, a count per tab from `badge` (none when it
 * returns null or ''), and `end` after the tabs (a view's filter). `pick` is
 * called with a tab clicked. Each tab controls the element with the id `panel`.
 * The arrow keys, Home and End move the focus between the tabs (a
 * `RovingFocusController` over `.tab` in the host); Enter and Space select one.
 */
export function tabBar(
  tabs: TabInfo[],
  current: Tab,
  badge: (id: Tab) => [string | number, Tone] | null,
  pick: (id: Tab) => void,
  panel: string,
  end: unknown = nothing,
): TemplateResult {
  return html`<nav>
    <div class="tabscroll" data-scroll="x">
      <div class="tabs" role="tablist" aria-label=${msg('Views', { desc: 'The label of the list of tabs: Overview, Tasks, History, ...' })}>
        ${tabs.map((t, i) => {
          const b = badge(t.id);
          const sel = t.id === current;
          return html`${t.panel && !tabs[i - 1]?.panel ? html`<span class="tab-sep" aria-hidden="true"></span>` : nothing}
            <button type="button" role="tab" id=${tabId(i)} aria-selected=${sel ? 'true' : 'false'} aria-controls=${panel}
              class="tab ${t.panel ? 'panel-tab' : ''} ${sel ? 'sel' : ''}" title=${t.tip ?? nothing} @click=${() => pick(t.id)}>
              <span class="tab-label" data-label=${t.label}>${t.label}</span>${b && b[0] !== '' ? html`<span class="badge" data-tone=${toneAttr(b[1])}>${b[0]}</span>` : nothing}
            </button>`;
        })}
        <span class="tab-ind" aria-hidden="true"></span>
      </div>
    </div>
    ${end}
  </nav>`;
}

/** When the selection changed, scroll the tab list so the selected tab is in view (after a render). */
export function revealTab(root: ParentNode): void {
  const sel = root.querySelector<HTMLElement>('.tab.sel');
  const list = root.querySelector<HTMLElement>('.tabscroll');
  if (!sel || !list || list.dataset['tab'] === sel.id) return;
  list.dataset['tab'] = sel.id;
  const edge = 24;
  if (sel.offsetLeft - edge < list.scrollLeft) list.scrollLeft = Math.max(0, sel.offsetLeft - edge);
  else if (sel.offsetLeft + sel.offsetWidth + edge > list.scrollLeft + list.clientWidth) list.scrollLeft = sel.offsetLeft + sel.offsetWidth + edge - list.clientWidth;
}

export const tabStyles = css`
  nav { flex: none; display: flex; align-items: stretch; gap: 4px 16px; padding: 0 24px; border-bottom: 1px solid var(--line); }
  /* Scroll shades: a cover at each end of the tabs (moves with them) over a shade at each edge of the list (stays):
     the shade shows at an edge while more tabs lie past it. */
  .tabscroll { flex: 1 1 auto; min-width: 0; display: flex; overflow-x: auto; scrollbar-width: none;
    --shade: color-mix(in srgb, var(--text) 26%, transparent);
    background:
      linear-gradient(to right, var(--bg) 40%, transparent) left / 32px 100% no-repeat local,
      linear-gradient(to left, var(--bg) 40%, transparent) right / 32px 100% no-repeat local,
      radial-gradient(farthest-side at 0 50%, var(--shade), transparent) left / 12px 100% no-repeat scroll,
      radial-gradient(farthest-side at 100% 50%, var(--shade), transparent) right / 12px 100% no-repeat scroll; }
  /* an older Safari, which hides the bar this way only */
  .tabscroll::-webkit-scrollbar { display: none; }
  .tabs { position: relative; flex: none; display: flex; gap: 22px; align-items: stretch; }
  /* The line under the selected tab is its border, so it stays in forced colours. */
  .tab { background: none; border: 0; padding: 11px 1px; color: var(--text-muted); cursor: pointer;
    font-weight: 500; white-space: nowrap; transition: color 0.15s; display: inline-flex; align-items: baseline; gap: 6px; }
  .tab:hover { color: var(--text-2); }
  .tab.sel { color: var(--text); font-weight: 600; padding-block-end: 9px; border-block-end: 2px solid var(--accent); }
  /* The label keeps the width of its bold form, so the tabs do not move when the selection does. */
  .tab-label { display: inline-flex; flex-direction: column; }
  .tab-label::after { content: attr(data-label); content: attr(data-label) / ''; font-weight: 600; height: 0; overflow: hidden; visibility: hidden; }
  /* a count: a number after the name; the count of what runs now in its colour */
  .badge { font-size: var(--font-size-xs); font-weight: 500; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .badge[data-tone] { padding: 0 6px; border-radius: var(--radius-pill); background: var(--tone-bg); color: var(--tone); }
  .tab-sep { width: 1px; background: var(--line2); margin: 10px 0; flex: none; }
  .tab-ind { display: none; }
  /* Where the browser can tie one element's place to another's, the line slides from the tab left to the tab chosen. */
  @supports (anchor-name: --a) {
    @media (prefers-reduced-motion: no-preference) and (forced-colors: none) {
      .tab.sel { anchor-name: --ca-tab; padding-block-end: 11px; border-block-end: 0; }
      .tab-ind { display: block; position: absolute; bottom: 0; height: 2px; left: anchor(--ca-tab left); right: anchor(--ca-tab right);
        background: var(--accent); border-radius: 2px 2px 0 0; transition: left 0.22s var(--ease), right 0.22s var(--ease); }
    }
  }
  /* what the view filters by: at the end of the tabs' line; under the tabs in a narrow monitor */
  .filter { flex: none; display: flex; gap: 8px; align-items: center; padding: 5px 0; }
  .filter select, .filter input { height: 28px; background: var(--card); color: var(--text); border: 1px solid var(--line-field); border-radius: var(--radius-md);
    padding: 0 8px; font: inherit; }
  .filter input { width: 22ch; }
  .filter :is(input, select):focus-visible { outline-offset: 0; }
  .filter .meta { white-space: nowrap; }
  .filter .meta:empty { display: none; }
  @container ca-monitor (max-width: 900px) {
    nav { flex-wrap: wrap; }
    .tabscroll { flex-basis: 100%; }
    .filter { flex: 1 1 100%; min-width: 0; border-top: 1px solid var(--line); margin: 0 -24px; padding: 8px 24px; }
    .filter select { flex: 0 1 auto; min-width: 0; }
    .filter input { flex: 1 1 0; min-width: 0; width: 0; }
  }
  @container ca-monitor (max-width: 760px) {
    nav { padding: 0 12px; }
    .tabs { gap: 18px; }
    .filter { margin: 0 -12px; padding: 8px 12px; }
  }
  /* a touch screen: a field's text at 16px, so the browser does not zoom the page to it */
  @media (pointer: coarse) {
    .filter select, .filter input { height: 36px; font-size: max(1rem, var(--font-size-sm)); }
    .tab { padding-block: 14px; }
    .tab.sel { padding-block-end: 12px; }
  }
`;
