// The demo pipeline's runs (demo agent, no pauses): failover, resends, refused
// inputs, transcripts and contracts for the monitor to show.
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export default function globalSetup(): void {
  const where = fileURLToPath(new URL('./.runs/', import.meta.url));
  // Made anew every time: runs left from older code would test what that code wrote.
  rmSync(where, { recursive: true, force: true });
  mkdirSync(where, { recursive: true });
  const project = fileURLToPath(new URL('../..', import.meta.url));
  // An earlier run of the nested flow over one more bundle: the forecast of the demo's `analyse` run.
  execFileSync('uv', ['run', '--project', project, 'python', fileURLToPath(new URL('./earlier.py', import.meta.url))], {
    cwd: where,
    stdio: 'inherit',
  });
  execFileSync('uv', ['run', '--project', project, 'python', '-m', 'contraagent.docs.examples.demo.run', '--no-serve', '--fast'], {
    cwd: where,
    stdio: 'inherit',
  });
}
