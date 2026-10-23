// What `<cae-transcript>` shows: a conversation with an agent in sections (one
// session each), each a list of items: chat bubbles, reasoning, notices and
// tool cards.
import type { Tone } from '../core/tone.js';

/** A page a tool returned (a web search's results). */
export interface ToolLink {
  title: string;
  url: string;
}

/** One tool call: the card that opens on its start and shows its result. */
export interface ToolCard {
  type: 'tool';
  id: string;
  name: string;
  /**
   * The card's glyph: `bash`, `read`, `grep`, `glob`, `edit`, `write`, `task`
   * or `agent`; any other key shows ⚒. A web search (`query`) and a page read
   * (`page`) have their own. Set as `data-tool` on the card.
   */
  icon: string;
  /** One line: the command, pattern, path or URL. */
  summary: string;
  /** Why the call was made, beside the summary. */
  intent?: string;
  /** A web search's query: shown above the pages it returned (`links`). */
  query?: string;
  /** A page the call read: its URL, a link when it is http(s). */
  page?: string;
  /** The command in full, above the output (not for a `query` or a `page`). */
  body?: string;
  /** The result; null while the call runs. */
  output: string | null;
  status: 'running' | 'ok' | 'error';
  /** The pages the call returned: listed as links, and counted beside the summary. */
  links?: readonly ToolLink[];
}

export type TranscriptItem =
  /** A prompt sent to the agent: its length, the start of it as a tooltip. */
  | { type: 'prompt'; id: string; text: string }
  /** The agent's answer, in markdown. */
  | { type: 'message'; id: string; text: string }
  /** The model's reasoning, in markdown. */
  | { type: 'reasoning'; id: string; text: string }
  /** Something that happened in the session, as a bubble: a glyph, a title and a detail. */
  | { type: 'event'; id: string; icon: string; title: string; text?: string }
  /** A line of the agent's own log. */
  | { type: 'notice'; id: string; text: string }
  | ToolCard;

/** A labelled value in a section's head (who ran it). */
export interface TranscriptTag {
  label: string;
  value: string;
  tip?: string;
  /** `mono`: the value in the monospace font; `quiet`: monospace, muted and without a background. */
  look?: 'mono' | 'quiet';
}

/** A folded text in a section's head: code (a command line) or prose (a prompt, drawn by `renderDetail`). */
export interface TranscriptDetail {
  id: string;
  summary: string;
  text: string;
  code?: boolean;
}

export interface TranscriptSection {
  id: string;
  /** Its name in the section picker. */
  title: string;
  /** Short facts after the title in the picker (a model). */
  facts?: readonly string[];
  /** How the section ended, in the picker: ✓ with tone `done`, else ✕; `text` for screen readers, `tip` as its tooltip. */
  verdict?: { tone: Tone; text: string; tip?: string };
  /** The section is still being written: a dot in the picker. */
  active?: boolean;
  /** Chips at the head of the section. */
  tags?: readonly TranscriptTag[];
  /** Folded texts at the head of the section. */
  details?: readonly TranscriptDetail[];
  items: readonly TranscriptItem[];
  /** A box after the items: how the section ended, and a list (errors) or a note. */
  footer?: { tone: Tone; title: string; list?: readonly string[]; note?: string };
}

/** Where the reader was in a transcript. */
export interface TranscriptScroll {
  /** Following the end. */
  stick: boolean;
  top: number;
}

/**
 * Where a host keeps what the reader did across visits: the open tool cards
 * and the scroll position. Without one, they last as long as the element.
 */
export interface TranscriptMemory {
  isOpen(id: string): boolean;
  setOpen(id: string, open: boolean): void;
  /** The position to restore when the content first arrives; undefined: the end. */
  scroll(): TranscriptScroll | undefined;
  setScroll(at: TranscriptScroll): void;
}

export interface TranscriptStrings {
  /** The section picker's accessible name (not shown). */
  sections: string;
  /** The section picker's tooltip. */
  sectionsTip: string;
  /** The button above the content when `earlier` is above 0. */
  loadEarlier: (n: number) => string;
  /** The button shown when `n` items arrived below while the reader was scrolled up. */
  newBelow: (n: number) => string;
  /** As `newBelow`, while another section than the latest is shown. */
  newInLatest: (n: number) => string;
  prompt: string;
  /** The name of the agent's messages: their avatar's accessible name and tooltip (no head is shown). */
  assistant: string;
  reasoning: string;
  characters: (n: number) => string;
  /** A tool card's name when the call has none. */
  tool: string;
  /** The number of `links` beside a card's summary. */
  results: (n: number) => string;
  done: string;
  failed: string;
  running: string;
  /** A call with no result in a transcript that is not `live`. */
  interrupted: string;
  interruptedTip: string;
  /** The label of a web search's query. */
  query: string;
  /** The label of a page's URL. */
  page: string;
  /** The fold of a web search's full output under its links. */
  fullText: string;
  showAll: (n: number) => string;
  showLess: string;
}

const plural = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`);

export const DEFAULT_TRANSCRIPT_STRINGS: Readonly<TranscriptStrings> = {
  sections: 'Sessions',
  sectionsTip: '',
  loadEarlier: (n) => `Show ${plural(n, 'earlier line', 'earlier lines')}`,
  newBelow: (n) => `Show ${plural(n, 'new event', 'new events')}`,
  newInLatest: (n) => `Show ${plural(n, 'new event', 'new events')} in the latest session`,
  prompt: 'Prompt',
  assistant: 'Assistant',
  reasoning: 'Reasoning',
  characters: (n) => `${n} characters`,
  tool: 'tool',
  results: (n) => plural(n, 'result', 'results'),
  done: 'done',
  failed: 'failed',
  running: 'running',
  interrupted: 'interrupted',
  interruptedTip: 'Ended with no result',
  query: 'query',
  page: 'page',
  fullText: 'Full text',
  showAll: (n) => `Show all (${n} characters)`,
  showLess: 'Show less',
};
