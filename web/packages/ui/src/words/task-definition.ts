// Words for the facts of a task definition that need more than a label: a Python
// task's retries, the parts of an output file it keeps, another kind's output it writes,
// the kind it is one implementation of.
import { msg, str } from '@lit/localize';

/** The label of a Python task's retries. */
export const retriesLabel = (): string => msg('Retries');

/** A number of retries: `up to 2`. */
export const retriesText = (n: number): string => msg(str`up to ${n}`, { desc: 'A number of retries' });

/** The label of the exceptions that give a Python task another attempt. */
export const retriedExceptionsLabel = (): string => msg('Retried exceptions');

/** What they are, for their tooltip. */
export const retriedExceptionsTip = (): string => msg('Exceptions that give another attempt (retry_on)');

/** The label of the parts of an output file a task must keep as they were (`preserve`). */
export const preserveLabel = (): string => msg('Must stay unchanged');

/** What they are, for their tooltip. */
export const preserveTip = (): string => msg('Parts of the output file kept as before the task (preserve)');

/** The output of another kind that a task writes in place of its own (`output_of`): `output of draft`. */
export const outputOfText = (kind: string): string => msg(str`output of ${kind}`, { desc: "Another kind's output file that this task writes" });

/** What that is, for its tooltip. */
export const outputOfTip = (): string => msg('The kind whose output file this task writes (output_of)');

/** The label of the kind an implementation kind is one implementation of (`base_kind`). */
export const implementationOfLabel = (): string => msg('Implementation of', { desc: 'A task definition: the kind that this kind is one implementation of' });

/** An implementation kind, in a list of kinds: `Implementation of review`. */
export const implementationOfText = (kind: string): string => msg(str`Implementation of ${kind}`);

/** What a base kind is, for its tooltip. */
export const implementationOfTip = (): string => msg('A kind that other kinds implement (base_kind)');
