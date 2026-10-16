// Code: a hand-written script, numbered from line 12, two of its lines marked; and
// the same element on a text too long to show whole.
import '@contraagent/elements/code/define';

const script = `def build(target: str, jobs: int = 4) -> bool:
    """Build one target; True when it passed."""
    result = run(["make", f"-j{jobs}", target])
    if result.returncode != 0:
        log.error("build of %s failed", target)  # the log names the target
        return False
    return True
`;

export function mount(host: HTMLElement): void {
  const code = document.createElement('cae-code');
  code.code = script;
  code.language = 'python';
  code.path = 'ci/build.py';
  code.start = 12;
  code.highlight = [15, [16, 17]];

  const long = document.createElement('cae-code');
  long.code = Array.from({ length: 40 }, (_, i) => `step ${i + 1}: ok`).join('\n');
  long.path = 'logs/steps.txt';
  long.maxLines = 6;
  long.style.marginTop = '12px';
  host.replaceChildren(code, long);
}
