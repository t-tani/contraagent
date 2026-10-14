// Words for a task's claims: the names it holds while it runs (`claims`), shown as its locks.
import { msg, str } from '@lit/localize';
import { facts, listText } from './format.js';

/** The label before a task's claims. */
export const locksLabel = (): string => msg('Locks');

/** What a task's claims are, for a tooltip. */
export const locksTip = (): string => msg('Names this task holds while it runs (claims)');

/** A task's claims in a row of the tasks list: by name, or how many when more than two. */
export const locksShort = (names: readonly string[]): string =>
  names.length > 2 ? msg(str`Locks ${names.length} names`) : msg(str`Locks ${listText(names)}`);

/** The tooltip of `locksShort`: what they are, and every name. */
export const locksNames = (names: readonly string[]): string => facts(locksTip(), listText(names));
