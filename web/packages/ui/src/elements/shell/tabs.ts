// The monitor's tab list: the built-in views, then the custom views; each tab
// with its count, and the line under the selected one.
import type { Info } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { css, html, nothing, type TemplateResult } from 'lit';
import { toneAttr } from '@contraagent/elements';
import type { Tab } from '../../core/route.js';
import type { Tone } from '../../lib/tone.js';

export interface TabInfo {
  id: Tab;
  label: string;
  icon: string;
  tip?: string;
  panel: boolean;
}

/** The built-in tabs, in the current locale (call at render time). */
const builtinTabs = (): Omit<TabInfo, 'panel'>[] => [
  { id: 'overview', label: msg('Overview'), icon: '◎' },
  { id: 'tasks', label: msg('Tasks', { id: 'tab-tasks', desc: 'Tab: the list of tasks' }), icon: '≡' },
  { id: 'journal', label: msg('History'), icon: '▤', tip: 'journal.jsonl' },
  { id: 'outputs', label: msg('Outputs'), icon: '▣' },
  { id: 'definitions', label: msg('Definitions'), icon: '⌘' },
  { id: 'procs', label: msg('Processes'), icon: '⚙' },
  { id: 'stream', label: msg('Task detail'), icon: '✦' },
];

/** Every tab, in the current locale: the built-in ones, then one per custom view (`panels`). */
export function monitorTabs(panels: Info['panels']): TabInfo[] {
  return [
    ...builtinTabs().map((t) => ({ ...t, panel: false })),
    ...panels.map((p) => ({
      id: `panel:${p.name}` as Tab,
      label: p.title || p.name,
      icon: p.icon || '▤',
      tip: p.description ? msg(str`${p.description} (custom view)`) : msg('Custom view'),
      panel: true,
    })),
  ];
}

/**
 * The tab list: `current` selected, a count per tab from `badge` (none when it
 * returns null or ''), and the key hints. `pick` is called with a tab clicked.
 */
export function tabBar(
  tabs: TabInfo[],
  current: Tab,
  badge: (id: Tab) => [string | number, Tone] | null,
  pick: (id: Tab) => void,
): TemplateResult {
  return html`<nav>
    ${tabs.map((t, i) => {
      const b = badge(t.id);
      return html`${t.panel && !tabs[i - 1]?.panel ? html`<span class="tab-sep" title=${msg('Custom views')}></span>` : nothing}
        <button type="button" class="tab ${t.panel ? 'panel-tab' : ''} ${t.id === current ? 'sel' : ''}" title=${t.tip ?? nothing}
          @click=${() => pick(t.id)}>
          <span class="tab-ic" aria-hidden="true">${t.icon}</span>${t.label}${b && b[0] !== '' ? html`<span class="badge" data-tone=${toneAttr(b[1])}>${b[0]}</span>` : nothing}
        </button>`;
    })}
    <span class="tab-ind init"></span>
    <span class="tabhint meta" role="note" aria-label=${msg('Keyboard shortcuts')}
      ><span aria-hidden="true"><span class="kbd">1</span>–<span class="kbd">${Math.min(9, tabs.length)}</span> ${msg('Tabs')} |
        <span class="kbd">r</span> ${msg('Runs')} | <span class="kbd">/</span> ${msg('Filter')}</span></span
    >
  </nav>`;
}

/** Move the line under the selected tab to it (after a render, a resize). */
export function moveTabIndicator(root: ParentNode): void {
  const sel = root.querySelector<HTMLElement>('.tab.sel');
  const ind = root.querySelector<HTMLElement>('.tab-ind');
  if (!sel || !ind) return;
  ind.style.left = `${sel.offsetLeft + 10}px`;
  ind.style.width = `${Math.max(12, sel.offsetWidth - 20)}px`;
  if (ind.classList.contains('init')) requestAnimationFrame(() => ind.classList.remove('init'));
}

export const tabStyles = css`
  nav { flex: none; display: flex; gap: 2px; padding: 6px 18px 0; position: relative; overflow-x: auto; scrollbar-width: none; align-items: center; }
  nav::-webkit-scrollbar { display: none; }
  .tab { position: relative; background: none; border: none; padding: 8px 14px 11px; color: var(--text-muted); cursor: pointer;
    font-weight: 500; white-space: nowrap; transition: color 0.2s; }
  .tab:hover { color: var(--text-2); }
  .tab.sel { color: var(--text); }
  .tab-ic { opacity: 0.55; margin-right: 6px; font-size: 12px; }
  .tab.sel .tab-ic { opacity: 1; color: var(--accent); }
  .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); font-variant-numeric: tabular-nums; }
  .badge[data-tone] { background: var(--tone-bg); color: var(--tone); }
  .tab-sep { width: 1px; height: 18px; background: var(--line2); margin: 0 8px 3px; flex: none; align-self: center; }
  .tab-ind { position: absolute; bottom: 0; left: 0; width: 0; height: 2px; border-radius: 2px;
    background: var(--accent); transition: left 0.3s var(--ease), width 0.3s var(--ease); }
  .tab-ind.init { transition: none; }
  .tabhint { margin-left: auto; padding-left: 12px; white-space: nowrap; }
`;
