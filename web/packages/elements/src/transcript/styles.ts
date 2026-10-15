import { css } from 'lit';

export const transcriptStyles = css`
  :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
  :host([mode='none']) { display: none; }
  :host([mode='tabs']) { flex: none; }
  :host([mode='tabs']) .scroller, :host([mode='tabs']) .newpill { display: none; }

  .rounds { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 10px; padding-left: 2px; }
  .rounds-lbl { color: var(--text-muted); font-size: 11.5px; font-weight: 600; margin-right: 4px; cursor: help; }
  .stab { padding: 3px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--card); color: var(--text-muted);
    cursor: pointer; font-size: 12px; display: inline-flex; align-items: center; }
  .stab:hover { border-color: var(--accent); }
  .stab.sel { background: var(--accent-bg); border-color: var(--accent); color: var(--text); }
  .stab-m { font-family: var(--mono); font-size: 10.5px; color: var(--text-muted); margin-left: 4px; }
  /* on the selected tab's tint, the secondary words take the secondary text colour, which reads on it */
  .stab.sel .stab-m { color: var(--text-2); }
  .stab .dot { width: 6px; height: 6px; margin-left: 4px; }
  .stab .mk { margin-right: 4px; }
  .stab .mk.ok { color: var(--status-done); }
  .stab .mk.bad { color: var(--status-failed); }
  .verdict { margin: 6px 10px 4px 41px; padding: 7px 11px; border-radius: 10px; border: 1px solid; font-size: 12px; }
  .verdict[data-tone] { background: var(--tone-bg); color: var(--text); }
  .verdict[data-tone='attention'] { border-color: color-mix(in srgb, var(--tone) 40%, transparent); }
  .verdict[data-tone='failed'] { border-color: color-mix(in srgb, var(--tone) 45%, transparent); }
  .verdict b { display: block; margin-bottom: 2px; }
  .verdict ul { margin: 2px 0 0; padding-left: 18px; font-family: var(--mono); font-size: 11.5px; }

  .scroller { flex: 1 1 auto; min-height: 0; overflow: auto; border: 1px solid var(--line); border-radius: 14px;
    background: linear-gradient(180deg, var(--panel), var(--well)); padding: 4px 2px 8px; font-size: 12.5px; }
  .back { margin: 6px 10px; background: var(--raise); border: 1px solid var(--line2); border-radius: 8px; padding: 3px 10px; cursor: pointer; color: var(--text-2); }
  .back:hover { border-color: var(--accent); }

  .inv-body { display: flex; flex-direction: column; gap: 10px; }
  .inv-head { border: 1px solid var(--line2); border-radius: 12px; background: var(--raise); padding: 8px 10px; margin: 4px 8px 6px; }
  .inv-who { display: flex; flex-wrap: wrap; gap: 6px; }
  .inv-cmdbox { margin-top: 6px; }
  .inv-cmdbox summary, .inv-prompt summary { cursor: pointer; font-size: 11px; color: var(--text-muted); }
  .inv-prompt summary { font-size: 11.5px; }
  .inv-prompt summary:hover { color: var(--accent); }
  .inv-cmd { font-family: var(--mono); font-size: 11.5px; white-space: pre-wrap; word-break: break-all; margin: 4px 0 6px; max-height: 160px; overflow: auto; color: var(--text); }
  .inv-ptext { margin-top: 6px; max-height: 360px; overflow: auto; }

  .msg { display: flex; gap: 9px; padding: 3px 10px; }
  .av { width: 22px; height: 22px; flex: 0 0 22px; border-radius: 7px; line-height: 22px; font-size: 11px; text-align: center; font-weight: 700; }
  .av-a { background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
  .av-l { background: var(--raise); color: var(--text-2); }
  .av-t { background: var(--raise); color: var(--text-muted); }
  .bd { flex: 1; min-width: 0; background: color-mix(in srgb, var(--text) 2.5%, transparent); border: 1px solid var(--line); border-radius: 3px 10px 10px 10px; padding: 5px 10px; }
  .hd { font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 1px; }
  .tx { color: var(--text); line-height: 1.5; word-break: break-word; }
  .tx pre, .tx code { white-space: pre-wrap; }
  .tx pre { margin: 0 0 4px; }

  .toolcard, .typing { margin-left: 41px; margin-right: 10px; }
  .toolcard { border: 1px solid var(--line); border-left: 3px solid var(--line2); border-radius: 10px; margin-top: 3px; margin-bottom: 3px;
    overflow: hidden; background: var(--well); transition: border-color 0.3s; }
  .toolcard.run { border-left-color: var(--status-running); }
  .toolcard.err { border-left-color: var(--status-failed); }
  .th { display: flex; gap: 9px; align-items: baseline; padding: 4px 9px; cursor: pointer; }
  .th:hover { background: color-mix(in srgb, var(--text) 4%, transparent); }
  .tn { font-family: var(--mono); font-weight: 600; flex: none; display: inline-flex; align-items: center; }
  .tn::before { content: '⚒'; display: inline-grid; place-items: center; width: 20px; height: 20px; margin-right: 7px;
    border-radius: 6px; background: var(--raise); color: var(--text-2); font-size: 11px; }
  /* a tool's icon: its shape tells the tool; the colour stays neutral (a colour is a status) */
  .toolcard[data-tool='bash'] .tn::before { content: '❯'; }
  .toolcard[data-tool='read'] .tn::before { content: '▤'; }
  .toolcard[data-tool='grep'] .tn::before, .toolcard[data-tool='glob'] .tn::before { content: '⌕'; }
  .toolcard[data-tool='edit'] .tn::before, .toolcard[data-tool='write'] .tn::before { content: '✎'; }
  .toolcard[data-tool='task'] .tn::before, .toolcard[data-tool='agent'] .tn::before { content: '✦'; color: var(--agent); }
  .toolcard[data-tool='web-search'] .tn::before { content: '◍'; }
  .toolcard[data-tool='web-fetch'] .tn::before { content: '⇣'; }
  .toolcard.revealed { box-shadow: 0 0 0 1px var(--accent); }
  .tp { font-family: var(--mono); font-size: 11.5px; color: var(--text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ti { color: var(--text-muted); font-size: 11px; flex: none; max-width: 35%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .st-run, .st-ok, .st-err, .st-int { flex: none; white-space: nowrap; }
  .st-run { color: var(--status-running); display: inline-flex; align-items: center; gap: 6px; }
  .st-ok { color: var(--text-muted); }
  .st-ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .st-err { color: var(--status-failed); }
  .st-int { color: var(--status-attention); }
  .pdot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--status-running); animation: breathe 1.8s ease-in-out infinite; }
  .tb { padding: 6px 9px; border-top: 1px solid var(--line); background: var(--bg); }
  .tb pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0; font-family: var(--mono); font-size: 12px; }
  .fold { max-height: 220px; overflow: hidden; position: relative; }
  .fold.open { max-height: none; }
  .foldbtn { cursor: pointer; color: var(--accent); font-size: 11px; background: none; border: 0; padding: 0; font-family: inherit; }
  .wq { font-size: 12px; margin: 2px 0 6px; }
  .wq b { font-family: var(--mono); font-weight: 600; }
  .wl { color: var(--text-muted); font-size: 11px; margin-right: 6px; }
  .links { margin: 0 0 6px; padding-left: 30px; font-size: 12px; }
  .links li { margin: 2px 0; overflow-wrap: anywhere; }
  .links a { color: var(--accent); text-decoration: none; }
  .links a:hover { text-decoration: underline; }
  .rawfold > summary { cursor: pointer; color: var(--text-muted); font-size: 11px; }
  .plink { color: var(--accent); text-decoration: none; font-family: var(--mono); overflow-wrap: anywhere; }
  .plink:hover { text-decoration: underline; }
  .host { color: var(--text-muted); font-family: var(--mono); font-size: 11px; margin-left: 6px; }

  .sysline { display: flex; gap: 8px; align-items: baseline; padding: 2px 10px 2px 41px; font-size: 11px; color: var(--text-muted); font-family: var(--mono); }
  .sysline .tx { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .typing { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
  .typing .av { width: 26px; height: 26px; flex: 0 0 26px; border-radius: 9px; display: grid; place-items: center; font-size: 12px; }
  .dots { display: inline-flex; gap: 4px; padding: 8px 12px; border-radius: 12px; background: var(--agent-bg); }
  .dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--agent); animation: bounce 1.2s infinite ease-in-out; }
  .dots i:nth-child(2) { animation-delay: 0.15s; }
  .dots i:nth-child(3) { animation-delay: 0.3s; }
  .scroller:not(.bulk) .msg, .scroller:not(.bulk) .toolcard { animation: enter 0.35s var(--ease) both; }

  .newpill { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 5; cursor: pointer; padding: 6px 14px;
    border-radius: 999px; border: 1px solid var(--accent); background: color-mix(in srgb, var(--panel) 92%, transparent); color: var(--accent);
    font-size: 12px; font-weight: 600; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 50%, transparent); backdrop-filter: blur(6px); animation: toast-in 0.3s var(--ease) both; }
  .newpill:hover { background: var(--accent-bg); }
`;
