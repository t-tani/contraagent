// Words for a task's tags: the named resources it holds while it runs (`tags`).
import { msg } from '@lit/localize';

/** The label before a task's tags. */
export const tagsLabel = (): string => msg('Tags');

/** What tags are, for a tooltip. */
export const tagsTip = (): string => msg('Resources this task holds while it runs (tags)');
