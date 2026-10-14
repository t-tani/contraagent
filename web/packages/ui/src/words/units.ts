// Words for a task's extra units: the units it locks while it runs, besides its own (`extra_units`).
import { msg, str } from '@lit/localize';
import { facts, listText } from './format.js';

/** The label before a task's extra units. */
export const alsoLocksLabel = (): string => msg('Also locks');

/** What extra units are, for a tooltip. */
export const alsoLocksTip = (): string => msg('Units this task locks while it runs, besides its own unit (extra_units)');

/** A task's extra units in a row of the tasks list: by name, or how many when more than two. */
export const alsoLocksShort = (units: readonly string[]): string =>
  units.length > 2 ? msg(str`Also locks ${units.length} units`) : msg(str`Also locks ${listText(units)}`);

/** The tooltip of `alsoLocksShort`: what they are, and every name. */
export const alsoLocksNames = (units: readonly string[]): string => facts(alsoLocksTip(), listText(units));
