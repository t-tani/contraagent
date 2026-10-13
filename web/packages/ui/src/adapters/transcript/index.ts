// A task's transcript: its events folded into rounds (`applyTranscriptEvents`),
// the rounds as the reader counts them, and the sections `<cae-transcript>` shows.
export { agentLabel, launchWho, whoTags, type Who } from './who.js';
export {
  applyEvents as applyTranscriptEvents,
  emptyTranscript,
  type Item as TranscriptItem,
  type Round as TranscriptRound,
  type ToolItem as TranscriptToolItem,
  type Transcript,
} from './model.js';
export { checkMessage, checkName, classifyRounds, fixupErrors, isFixup } from './rounds.js';
export { webResults, type WebResult } from './web.js';
export { transcriptSections, type SectionsContext } from './sections.js';
