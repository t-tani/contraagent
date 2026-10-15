// Who ran a session: the coding agent (the CLI), the model and the role, read
// from its launch, and as the chips of a transcript section's head.
import type { LaunchEvent } from '@contraagent/api';
import type { TranscriptTag } from '@contraagent/elements/transcript';
import { msg } from '@lit/localize';

/** Who ran a round: the coding agent (the CLI), the model and the role. */
export interface Who {
  agent: string;
  model: string;
  role: string;
}

const AGENT_NAMES: Record<string, string> = {
  claude: 'Claude Code',
  omp: 'omp',
  codex: 'Codex',
  opencode: 'opencode',
  gemini: 'Gemini CLI',
};

/** The display name of a coding agent's executable (`/usr/bin/claude` -> `Claude Code`). */
export function agentLabel(exe: string | null | undefined): string {
  const b = String(exe || '').split('/').pop() ?? '';
  return AGENT_NAMES[b] ?? b;
}

const argvFlag = (argv: readonly string[], name: string): string => {
  const i = argv.indexOf(name);
  return i >= 0 ? (argv[i + 1] ?? '') : '';
};

/** Who ran a launch: its argv names the agent and model, its prompt's TELEMETRY line the role. */
export function launchWho(launch: Pick<LaunchEvent, 'argv' | 'prompt'>): Who {
  const argv = launch.argv;
  const tele = /TELEMETRY [^\n]*role=([\w:-]+)/.exec(launch.prompt || '');
  const role = tele?.[1];
  return {
    agent: agentLabel(argv[0]),
    model: argvFlag(argv, '--model') || argvFlag(argv, '-m'),
    role: role && role !== '-' ? role : '',
  };
}

/** The chips for who ran a session (`tagChips`), in the reader's language (call at render time). */
export function whoTags(w: Who | null | undefined): TranscriptTag[] {
  if (!w) return [];
  const tags: TranscriptTag[] = [];
  if (w.agent) tags.push({ label: msg('coding agent'), value: w.agent, tip: msg('The CLI that ran the task (claude, omp)') });
  if (w.model) tags.push({ label: msg('model'), value: w.model, tip: msg('The model the agent session ran on'), look: 'mono' });
  if (w.role) tags.push({ label: msg('role'), value: w.role, tip: msg('The agent definition the coding agent ran as (agents/<role>.md)'), look: 'quiet' });
  return tags;
}
