// Words for a task's own working directory (`PlanNode.cwd`): the directory its call options named.
import { msg, str } from '@lit/localize';

/** A task's own working directory as a fact: `Working directory /repo.worktrees/alpha`; '' for none (the run's). */
export const workingDirectoryText = (cwd: string | null | undefined): string => (cwd ? msg(str`Working directory ${cwd}`) : '');

/** What a task's own working directory is, for its tooltip. */
export const workingDirectoryTip = (): string => msg("Directory the task worked in, named by its task call in place of the run's (cwd)");
