// A task's transcript as `<cae-transcript>` shows it: a section per round,
// named as the reader counts rounds (attempt, correction, model switch), with
// how it ended, who ran it, its command line and prompt, and its items.
import { isLaunched, runRelative, type JournalRow, type LaunchEvent } from '@contraagent/api';
import type { TranscriptDetail, TranscriptItem, TranscriptSection } from '@contraagent/elements/transcript';
import { msg, str } from '@lit/localize';
import type { RoundInfo } from '../../core/events.js';
import { attemptNames } from '../../words/attempts.js';
import { roundLabel, roundMark, switchText } from '../../words/rounds.js';
import { stopLabel } from '../../words/stop.js';
import type { Transcript } from './model.js';
import { whoTags } from './who.js';

export interface SectionsContext {
  /** The run id: paths in a reason are shown relative to it. */
  run: string;
  /** The task's journal rows: the attempts' names. */
  rows: readonly JournalRow[];
  /** The latest round is still being written (the task runs and its transcript is tailed). */
  active: boolean;
}

/** The command line, and the prompt with what was not saved of it. */
function launchDetails(launch: LaunchEvent): TranscriptDetail[] {
  const prompt = launch.prompt || '';
  const trunc = launch.prompt_truncated || 0;
  return [
    { id: 'cmd', code: true, summary: msg('Command line'), text: launch.argv.join(' ') },
    {
      id: 'prompt',
      summary: trunc
        ? msg(str`Prompt (${prompt.length} characters; ${trunc} characters not saved)`)
        : msg(str`Prompt (${prompt.length} characters)`),
      text: prompt + (trunc ? `\n\n${msg(str`(${trunc} characters not saved)`)}` : ''),
    },
  ];
}

/** How the round ended, after its transcript: its output was sent back, its model switched, or its try failed. */
function footer(info: RoundInfo, run: string): TranscriptSection['footer'] {
  if (info.result === 'rejected') {
    return {
      tone: 'attention',
      title: msg('Output failed checks'),
      list: info.rejectedWith.map((e) => runRelative(e, run)),
      note: msg('The errors are in the correction prompt'),
    };
  }
  if (info.result === 'switched') return { tone: 'failed', title: switchText(info) };
  if (info.result === 'failed' && info.row) {
    const why = runRelative(info.row.reason, run) || stopLabel(info.row.stop);
    return { tone: 'failed', title: msg(str`Attempt ${info.tryNo} failed: ${why}`) };
  }
  return undefined;
}

/**
 * The sections of a transcript, one per round; `rounds` are the rounds as
 * `classifyRounds` counts them. In the reader's language: call at render time.
 */
export function transcriptSections(t: Transcript, rounds: readonly RoundInfo[], ctx: SectionsContext): TranscriptSection[] {
  const tries = rounds[rounds.length - 1]?.tryNo ?? 1;
  const names = attemptNames(ctx.rows.filter(isLaunched));
  const last = t.rounds.length - 1;
  return t.rounds.map((r, i) => {
    const info = rounds[i];
    const [mark, word, tip] = info ? roundMark(info, ctx.run) : ['', '', ''];
    const model = r.who?.model;
    return {
      id: r.id,
      title: info ? roundLabel(info, tries, names[info.tryNo - 1]) : String(i + 1),
      facts: model ? [model.replace(/^claude-/, '')] : [],
      verdict: mark ? { tone: mark === '✓' ? 'done' : 'failed', text: word, tip } : undefined,
      active: i === last && ctx.active,
      tags: r.launch ? whoTags(r.who) : [],
      details: r.launch ? launchDetails(r.launch) : [],
      // the model leaves an event's title to the reader's words: the only event is an API request sent again
      items: r.items.map((it): TranscriptItem => (it.type === 'event' ? { ...it, title: msg('API request sent again') } : it)),
      footer: info && footer(info, ctx.run),
    };
  });
}
