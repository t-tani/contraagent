import { css } from 'lit';

export const transcriptStyles = css`
  :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; container-type: inline-size; }
  :host([mode='none']) { display: none; }
  :host([mode='tabs']) { flex: none; }
  :host([mode='tabs']) .scroller, :host([mode='tabs']) .newpill { display: none; }

  .rounds { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 10px; padding-left: 2px; }
  .stab { padding: 3px 11px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--card); color: var(--text-muted);
    cursor: pointer; font-size: var(--font-size-xs); display: inline-flex; align-items: center; }
  .stab:hover { border-color: var(--accent); }
  .stab.sel { background: var(--accent-bg); border-color: var(--accent); color: var(--text); }
  .stab-m { font-family: var(--mono); font-size: var(--font-size-xs); color: var(--text-muted); margin-left: 4px; }
  /* on the selected tab's tint, the secondary words take the secondary text colour, which reads on it */
  .stab.sel .stab-m { color: var(--text-2); }
  @media (forced-colors: active) {
    .stab.sel { outline: 2px solid Highlight; outline-offset: -2px; }
  }
  .stab .dot { width: 6px; height: 6px; margin-left: 4px; }
  .stab .mk { margin-right: 4px; }
  .stab .mk.ok { color: var(--status-done); }
  .stab .mk.bad { color: var(--status-failed); }
  .verdict { margin: 6px 0 4px 32px; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid; font-size: var(--font-size-xs); }
  .verdict[data-tone] { background: var(--tone-bg); color: var(--text); }
  .verdict[data-tone='attention'] { border-color: color-mix(in srgb, var(--tone) 40%, transparent); }
  .verdict[data-tone='failed'] { border-color: color-mix(in srgb, var(--tone) 45%, transparent); }
  .verdict b { display: block; margin-bottom: 2px; }
  .verdict ul { margin: 2px 0 0; padding-left: 18px; font-family: var(--mono); font-size: var(--font-size-xs); }

  /* the transcript is the page's own text: no frame around it */
  .scroller { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 0 0 8px; font-size: var(--font-size-sm); }
  .back { margin: 6px 10px; background: var(--raise); border: 1px solid var(--line2); border-radius: var(--radius-md); padding: 3px 10px; cursor: pointer; color: var(--text-2); }
  .back:hover { border-color: var(--accent); }

  .inv-body { display: flex; flex-direction: column; gap: 10px; }
  .inv-head { border-bottom: 1px solid var(--line); padding: 2px 2px 10px; margin: 0 0 4px; }
  .inv-who { display: flex; flex-wrap: wrap; gap: 6px; }
  .inv-cmdbox { margin-top: 6px; }
  .inv-cmdbox summary, .inv-prompt summary { cursor: pointer; font-size: var(--font-size-xs); color: var(--text-muted); }
  .inv-prompt summary { font-size: var(--font-size-xs); }
  .inv-prompt summary:hover { color: var(--accent); }
  .inv-cmd { font-family: var(--mono); font-size: var(--font-size-xs); white-space: pre-wrap; word-break: break-all; margin: 4px 0 6px; max-height: 160px; overflow: auto; color: var(--text); }
  .inv-ptext { margin-top: 6px; max-height: 360px; overflow: auto; }

  .msg { display: flex; gap: 10px; padding: 5px 0; }
  .av { width: 22px; height: 22px; flex: 0 0 22px; border-radius: var(--radius-md); line-height: 22px; font-size: var(--font-size-xs); text-align: center; font-weight: 700; margin-top: 1px; }
  .av-a { background: var(--agent-bg); color: var(--agent); }
  .av-l { background: var(--raise); color: var(--text-2); }
  .av-t { background: var(--raise); color: var(--text-muted); }
  .bd { flex: 1; min-width: 0; padding: 1px 0; }
  .hd { font-size: var(--font-size-xs); font-weight: 600; color: var(--text-muted); margin-bottom: 1px; }
  .tx { color: var(--text); line-height: 1.5; word-break: break-word; }
  .tx pre, .tx code { white-space: pre-wrap; }
  .tx pre { margin: 0 0 4px; }

  .toolcard, .typing { margin-left: 32px; }
  .toolcard { border: 1px solid var(--line); border-radius: var(--radius-md); margin-top: 3px; margin-bottom: 3px;
    overflow: hidden; background: var(--card); transition: border-color 0.3s; }
  .toolcard.run { border-color: color-mix(in srgb, var(--status-running) 45%, var(--line)); }
  .toolcard.err { border-color: color-mix(in srgb, var(--status-failed) 45%, var(--line)); }
  .th { display: flex; gap: 9px; align-items: baseline; padding: 5px 10px; cursor: pointer; }
  .th:hover { background: color-mix(in srgb, var(--text) 4%, transparent); }
  .tn { font-family: var(--mono); font-weight: 600; flex: none; display: inline-flex; align-items: center; }
  .tn::before { content: '⚒'; content: '⚒' / ''; display: inline-grid; place-items: center; width: 16px; height: 20px; margin-right: 7px;
    color: var(--text-muted); font-size: var(--font-size-xs); font-weight: 400; }
  /* a tool's icon: its shape tells the tool; the colour stays neutral (a colour is a status) */
  .toolcard[data-tool='bash'] .tn::before { content: '❯'; content: '❯' / ''; }
  .toolcard[data-tool='read'] .tn::before { content: '▤'; content: '▤' / ''; }
  .toolcard[data-tool='grep'] .tn::before, .toolcard[data-tool='glob'] .tn::before { content: '⌕'; content: '⌕' / ''; }
  .toolcard[data-tool='edit'] .tn::before, .toolcard[data-tool='write'] .tn::before { content: '✎'; content: '✎' / ''; }
  .toolcard[data-tool='task'] .tn::before, .toolcard[data-tool='agent'] .tn::before { content: '✦'; content: '✦' / ''; color: var(--agent); }
  .toolcard[data-tool='web-search'] .tn::before { content: '◍'; content: '◍' / ''; }
  .toolcard[data-tool='web-fetch'] .tn::before { content: '⇣'; content: '⇣' / ''; }
  .toolcard.revealed { box-shadow: 0 0 0 1px var(--accent); }
  .tp { font-family: var(--mono); font-size: var(--font-size-xs); color: var(--text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* a path: its directories give way, its file name stays whole */
  .tp.path { display: flex; }
  .tp-a { flex: 0 1 auto; min-width: 3ch; overflow: hidden; text-overflow: ellipsis; color: var(--text-2); }
  .tp-z { flex: none; }
  .ti { color: var(--text-muted); font-size: var(--font-size-xs); flex: none; max-width: 35%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .st-run, .st-ok, .st-err, .st-int { flex: none; white-space: nowrap; }
  .st-run { color: var(--status-running); display: inline-flex; align-items: center; gap: 6px; }
  .st-ok { color: var(--text-muted); }
  .st-ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .st-err { color: var(--status-failed); }
  .st-int { color: var(--status-attention); }
  .pdot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--status-running); animation: breathe 1.8s ease-in-out infinite; }
  .tb { padding: 6px 10px; border-top: 1px solid var(--line); background: var(--well); }
  .tb pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0; font-family: var(--mono); font-size: var(--font-size-xs); }
  .fold { max-height: 220px; overflow: hidden; position: relative; }
  .fold.open { max-height: none; }
  .foldbtn { cursor: pointer; color: var(--accent); font-size: var(--font-size-xs); background: none; border: 0; padding: 0; font-family: inherit; }
  .wq { font-size: var(--font-size-xs); margin: 2px 0 6px; }
  .wq b { font-family: var(--mono); font-weight: 600; }
  .wl { color: var(--text-muted); font-size: var(--font-size-xs); margin-right: 6px; }
  .links { margin: 0 0 6px; padding-left: 30px; font-size: var(--font-size-xs); }
  .links li { margin: 2px 0; overflow-wrap: anywhere; }
  .links a { color: var(--accent); text-decoration: none; }
  .links a:hover { text-decoration: underline; }
  .rawfold > summary { cursor: pointer; color: var(--text-muted); font-size: var(--font-size-xs); }
  .plink { color: var(--accent); text-decoration: none; font-family: var(--mono); overflow-wrap: anywhere; }
  .plink:hover { text-decoration: underline; }
  .host { color: var(--text-muted); font-family: var(--mono); font-size: var(--font-size-xs); margin-left: 6px; }

  .sysline { display: flex; gap: 8px; align-items: baseline; padding: 2px 0 2px 32px; font-size: var(--font-size-xs); color: var(--text-muted); font-family: var(--mono); }
  .sysline .tx { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .typing { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
  .typing .av { width: 26px; height: 26px; flex: 0 0 26px; border-radius: var(--radius-md); display: grid; place-items: center; font-size: var(--font-size-xs); }
  .dots { display: inline-flex; gap: 4px; padding: 8px 12px; border-radius: var(--radius-lg); background: var(--agent-bg); }
  .dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--agent); animation: bounce 1.2s infinite ease-in-out; }
  .dots i:nth-child(2) { animation-delay: 0.15s; }
  .dots i:nth-child(3) { animation-delay: 0.3s; }
  .scroller:not(.bulk) .msg, .scroller:not(.bulk) .toolcard { animation: enter 0.35s var(--ease) both; }

  /* a phone: the cards start under the avatars, not after them, a tool's argument gets a line of its own, and what the agent meant by a call shows when its card is open */
  @container (max-width: 520px) {
    .msg { gap: 8px; }
    .toolcard, .typing { margin-left: 0; }
    .sysline { padding-left: 0; }
    .verdict { margin-left: 0; }
    .th { flex-wrap: wrap; row-gap: 2px; }
    .ti { flex: 1 1 0; max-width: none; text-align: end; }
    .ti.intent { visibility: hidden; }
    .st-run, .st-ok, .st-err, .st-int { margin-left: auto; }
    .th[aria-expanded='true'] .ti.intent { visibility: visible; order: 2; flex-basis: 100%; max-width: none; text-align: start; white-space: normal; }
    .tp { order: 1; flex: 1 1 100%; white-space: normal; overflow-wrap: anywhere;
      display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; }
    /* a path: its file name, the directories left out (the open card has the whole path) */
    .tp.path { order: 1; flex: 1 1 100%; }
    .tp-a { display: none; }
    .tp-z::before { content: '…'; content: '…' / ''; color: var(--text-muted); }
  }

  .newpill { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 5; cursor: pointer; padding: 6px 14px;
    border-radius: var(--radius-pill); border: 1px solid var(--accent); background: color-mix(in srgb, var(--panel) 92%, transparent); color: var(--accent);
    font-size: var(--font-size-xs); font-weight: 600; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 50%, transparent); backdrop-filter: blur(6px); animation: toast-in 0.3s var(--ease) both; }
  .newpill:hover { background: var(--accent-bg); }
`;
