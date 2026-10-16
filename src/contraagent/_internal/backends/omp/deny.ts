// contraagent's own omp extension: the tools a task may not use (`disallowed_tools`), denied
// inside omp. The omp backend loads it (`-e`) into a launch whose task denies a tool, with the
// rules in CONTRAAGENT_OMP_DENY as JSON (`backends/omp/deny.py`, `rules`, which documents
// each field). A
// whole tool is removed from the tools the model is offered when the session starts, and
// every call is checked before it runs (`tool_call`): a denied one is blocked, and the model
// is told which rule denied it.
import { homedir } from "node:os";
import { join, resolve } from "node:path";

type Rule = {
  rule: string;
  tools?: string[];
  prefix?: string;
  command?: string;
  path?: string;
  schemes?: string[];
  host?: string;
};
type Input = Record<string, unknown>;

const RULES: Rule[] = (() => {
  try {
    const parsed = JSON.parse(process.env.CONTRAAGENT_OMP_DENY ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
})();

// A rule that names a tool whole, and nothing of what the tool is given.
function whole(r: Rule): boolean {
  return r.command === undefined && r.path === undefined && r.schemes === undefined;
}

function names(r: Rule, tool: string): boolean {
  return (r.tools ?? []).includes(tool) || (r.prefix !== undefined && tool.startsWith(r.prefix));
}

// Each command of a shell line: the parts between `&&`, `||`, `;`, `|`, `&` and line ends.
function commands(line: string): string[] {
  return line
    .split(/&&|\|\||[;|&\n]/)
    .map(part => part.trim())
    .filter(part => part.length > 0);
}

function absolute(path: string, cwd: string): string {
  if (path === "~" || path.startsWith("~/")) return join(homedir(), path.slice(1));
  return resolve(cwd, path);
}

// The file paths a call names: `path`, `paths` and `file_path`, each also without a line
// selector (`file.ts:10-20`), resolved against the session's directory.
function paths(input: Input, cwd: string): string[] {
  const given: string[] = [];
  for (const key of ["path", "file_path"]) if (typeof input[key] === "string") given.push(input[key] as string);
  if (Array.isArray(input.paths)) for (const p of input.paths) if (typeof p === "string") given.push(p);
  const out: string[] = [];
  for (const p of given) {
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(p)) continue;
    out.push(absolute(p, cwd), absolute(p.replace(/:[^/]*$/, ""), cwd));
  }
  // The rules write a path with `/` between its parts, on Windows too.
  return out.map(p => p.replace(/\\/g, "/"));
}

function url(input: Input): URL | undefined {
  const p = input.path;
  if (typeof p !== "string" || !/^[a-z][a-z0-9+.-]*:\/\//i.test(p)) return undefined;
  try {
    return new URL(p);
  } catch {
    return undefined;
  }
}

function denies(r: Rule, tool: string, input: Input, cwd: string): boolean {
  if (!names(r, tool)) return false;
  if (r.schemes !== undefined) {
    const u = url(input);
    if (u === undefined || !r.schemes.includes(u.protocol.replace(/:$/, ""))) return false;
    if (r.host === undefined) return true;
    const host = u.hostname.toLowerCase();
    return host === r.host || host.endsWith(`.${r.host}`);
  }
  if (r.command !== undefined) {
    const re = new RegExp(r.command);
    return commands(String(input.command ?? "")).some(c => re.test(c));
  }
  if (r.path !== undefined) {
    const re = new RegExp(r.path);
    return paths(input, cwd).some(p => re.test(p));
  }
  return true;
}

export default function (pi: any): void {
  if (!RULES.length) return;
  pi.on("session_start", async () => {
    const wholes = RULES.filter(whole);
    if (!wholes.length) return;
    const active: string[] = pi.getActiveTools();
    const kept = active.filter(tool => !wholes.some(r => names(r, tool)));
    if (kept.length !== active.length) await pi.setActiveTools(kept);
  });
  pi.on("tool_call", async (event: any, ctx: any) => {
    const input = (event.input ?? {}) as Input;
    const cwd = String(ctx?.cwd ?? process.cwd());
    for (const r of RULES) {
      if (denies(r, String(event.toolName), input, cwd)) {
        return { block: true, reason: `denied by the task's disallowed_tools: ${r.rule}` };
      }
    }
  });
}
