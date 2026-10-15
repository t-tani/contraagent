// Words for the run's preflight (`Plan.preflight`): one request to each model of the
// run before its first agent session, and what became of the kinds whose models did not answer.
import type { Preflight, PreflightDropped, PreflightSubstitution } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { credentialLabel } from './credential.js';
import { facts, listText } from './format.js';

/** A route as the history names it: `agent / model`, the agent alone for its default model. */
export const routeName = (agent: string, model: string): string => (model ? `${agent} / ${model}` : agent);

/** The label of the preflight's facts. */
export const preflightLabel = (): string => msg('Model availability');

/** What the preflight is, for its tooltip, with its policy. */
export const preflightTip = (policy: Preflight['policy']): string =>
  msg(str`One request to each model before the first agent session (preflight, policy ${policy})`);

/** A preflight that dropped no model. */
export const allAvailable = (): string => msg('all models available');

/** A model that did not answer, or that its coding agent does not list (`dropped`). */
export const unavailableLabel = (): string => msg('Unavailable', { desc: 'A model that did not answer the request before the run' });

/** A dropped model in one row: `claude / opus | identity work | rate limited | kinds review and summarize`. */
export const unavailableText = (d: PreflightDropped): string =>
  facts(
    routeName(d.agent, d.model),
    d.credential ? msg(str`identity ${credentialLabel(d.credential)}`) : '',
    d.reason,
    d.kinds.length ? msg(str`kinds ${listText(d.kinds)}`) : '',
  );

/** A kind that runs on the first model that answered, in place of its own (`substituted`). */
export const replacedLabel = (): string => msg('Model replaced');

/** What a replaced model is, for its tooltip. */
export const replacedTip = (): string => msg('A kind with no available model, run on the first model that answered (substitute)');

/** A replaced model in one row: `review | claude / opus → claude / sonnet`. */
export const replacedText = (s: PreflightSubstitution): string =>
  facts(s.kind, `${routeName(s.from_agent, s.from_model)} → ${routeName(s.to_agent, s.to_model)}`);

/** A kind none of whose models is available (`kept`, `stopped`). */
export const noModelLabel = (): string => msg('No available model');

/** What a kept kind is, for its tooltip. */
export const keptTip = (): string => msg('A kind with no available model, run on its own model (kept)');

/** The title of a run the preflight ended before its first agent session (`stopped`). */
export const preflightStoppedTitle = (): string => msg('Ended before the first agent session');

/** The cause of that end: `No available model for review and summarize`. */
export const preflightStoppedCause = (kinds: readonly string[]): string => msg(str`No available model for ${listText(kinds)}`);
