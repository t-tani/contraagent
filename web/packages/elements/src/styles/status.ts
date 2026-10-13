// A status, by tone (core/tone.ts, primitives/pill.ts): one rule per tone, and
// the status elements that take it (a mark, a pill, a word, a dot, a spinner).
import { css } from 'lit';

export const statusStyles = css`
  /*
   * data-tone names its status colour, which each kind of status element below takes as
   * --tone (the colour) and --tone-bg (its tint). No data-tone: neutral.
   */
  [data-tone='failed'] { --tone: var(--status-failed); --tone-bg: var(--status-failed-bg); }
  [data-tone='attention'] { --tone: var(--status-attention); --tone-bg: var(--status-attention-bg); }
  [data-tone='done'] { --tone: var(--status-done); --tone-bg: var(--status-done-bg); }
  [data-tone='running'] { --tone: var(--status-running); --tone-bg: var(--status-running-bg); }
  [data-tone='muted'] { --tone: var(--status-muted); --tone-bg: var(--status-muted-bg); }

  /*
   * A status mark before a status word (data-mark): ✓ done, ✕ failed, ◌ not started or waiting.
   * The shape keeps the meaning without colour; screen readers read the word only.
   */
  [data-mark]::before { margin-right: 0.35em; font-weight: 700; }
  [data-mark='done']::before { content: '✓'; content: '✓' / ''; color: var(--status-done); }
  [data-mark='failed']::before { content: '✕'; content: '✕' / ''; }
  [data-mark='pending']::before { content: '◌'; content: '◌' / ''; }

  /* text in a status colour: only on a status that applies (a count above 0 of a problem, a status word) */
  .tone-text[data-tone] { color: var(--tone); }

  /*
   * A status as a pill, always with its word. A problem is tinted and marked (✕ failed, ◌ not started);
   * done is quiet (a ✓ and the word): it is the usual case, and the problems are what stand out.
   */
  .pill { border-radius: var(--radius-pill); padding: 1px 10px; font-size: var(--font-size-sm); font-weight: 500; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .pill[data-tone] { background: var(--tone-bg); color: var(--tone); }
  .pill[data-tone='done'] { background: none; padding-left: 2px; color: var(--text-2); }

  /* a status as a word in a row (History, Problems, Outputs): coloured for a problem, done quiet with its ✓ */
  .jstop { font-weight: 600; }
  .jstop[data-tone='failed'], .jstop[data-tone='attention'] { color: var(--tone); }
  .jstop[data-tone='done'] { color: var(--text-2); font-weight: 500; }

  /*
   * A status as a dot (a run in the header and the run list). The shape carries it too:
   * round done, square failed, diamond attention, a breathing ring running.
   */
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--line2); flex: none; display: inline-block; }
  .dot[data-tone] { background: var(--tone); }
  .dot[data-tone='running'] { animation: breathe 1.8s ease-in-out infinite; }
  .dot[data-tone='attention'] { border-radius: 1px; transform: rotate(45deg) scale(0.86); }
  .dot[data-tone='failed'] { border-radius: 1.5px; }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--status-running-bg);
    border-top-color: var(--status-running); animation: turn 0.9s linear infinite; flex: none; display: inline-block; }
`;
