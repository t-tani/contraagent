"""`contraagent` command line.

contraagent monitor [--runs-dir runs] [--port 8787]
contraagent monitor export --out site/stats [--runs 10]   # the monitor as files, served with no server
contraagent plugin new plugins/summarize [--name N]
contraagent plugin lint plugins          # a plugin, or a directory of plugins
contraagent plugin render <plugin>       # hooks.toml -> each coding agent's native hooks
contraagent plugin hook --agent codex --root DIR SCRIPT  # what a rendered Codex hook runs
contraagent call validate [--call PATH]  # what a plugin's Stop hook runs (default: $CONTRAAGENT_CALL)
contraagent check tasks.py:docs --config pipeline.toml --kwargs '{"units": ["alpha"]}'
                                         # a flow, checked without launching anything
contraagent run tasks.py:docs --config pipeline.toml --kwargs '{"units": ["alpha"]}' [--run-id ID] [--resume]
                                         [--preflight substitute|stop|off]
                                         # the same flow, run (exit 1 when a task or the flow failed)
contraagent run tasks.py:docs --stub [--execute PATTERN]
                                         # a stub run: the stub agent plays every task with its output's
                                         # example, and the tasks the flow created are listed
contraagent run tasks.py:docs --record DIR   # a run that keeps each task attempt's recording in DIR
contraagent run tasks.py:docs --replay DIR [--execute PATTERN] [--record-missing]
                                         # a replay: every task plays its recording, nothing is spent;
                                         # with --record-missing, a task with none runs and is recorded
contraagent recording import runs/docs DIR   # a recording of each task a run finished, from its directory
contraagent --version                    # the installed version
contraagent docs [TOPIC] [--path]        # the documentation installed with the package
contraagent docs --pointer >> AGENTS.md  # point a project's coding agent at it
contraagent relay --hub URL [--runs-dir runs]  # ship this host's runs to a hub
contraagent hub --ingest-token-file FILE [--store ...]  # receive every host's runs, serve their monitor
contraagent hub prune --retain-days N    # remove old runs from the hub's storage once

One argparse tree (`parser`). `monitor` (with `monitor export`), `relay` and `hub` (with
`hub prune`) live in their own modules, each with `add_arguments(parser)` and `run(args)`;
the option groups they share, `load_attr` and the errors a command reports are in
`contraagent._internal.commandline`.
"""

from __future__ import annotations

import argparse
import importlib
import io
import signal
import sys
from importlib import metadata
from pathlib import Path

from contraagent._internal.commandline import (
    CommandError,
    MissingExtra,
    UsageError,
    add_command,
    add_runs_dir,
    load_attr,
    setup_logging,
    split_spec,
)

#: The commands whose module holds their arguments and what they do (`add_arguments`,
#: `run`): imported only when the command line names them.
MODULES = {
    "monitor": ("contraagent._internal.monitor.server", "live web monitor for runs (see `contraagent monitor --help`)"),
    "relay": ("contraagent._internal.hub.relay", "ship this host's runs to a hub (see `contraagent relay --help`)"),
    "hub": ("contraagent._internal.hub.server", "receive every host's runs and serve their monitor (see `contraagent hub --help`)"),
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if sys.platform == "win32":
        # A pipe there carries the code page's text, not UTF-8: a hook's reasons, JSON on stdin.
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            if isinstance(stream, io.TextIOWrapper):
                stream.reconfigure(encoding="utf-8", errors="replace")
    args = parser(argv[0] if argv else None).parse_args(argv)
    if not args.serves and sys.platform != "win32":  # Windows has no SIGPIPE
        # Output piped into `head` ends quietly, as a command line tool's should.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        return args.run(args)
    except UsageError as exc:
        args.parser.error(str(exc))
    except (CommandError, MissingExtra) as exc:
        print(f"{args.parser.prog}: {exc}", file=sys.stderr)
    return 2


def parser(command: str | None = "") -> argparse.ArgumentParser:
    """The command line. A command of `MODULES` gets its arguments only when it is `command`
    (its module is imported only then); `""` gives every command its arguments."""
    ap = argparse.ArgumentParser(
        prog="contraagent",
        epilog="exit status: 0 on success, 1 when the command found a problem or a task failed, 2 on a usage error; "
        "`contraagent <command> --help` says what each command's means",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {metadata.version('contraagent')}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (module, help) in MODULES.items():
        if command == "" or command == name:
            mod = importlib.import_module(module)
            add_command(sub, name, help=help, add_arguments=mod.add_arguments, run=mod.run, serves=True)
        else:
            sub.add_parser(name, help=help)

    plugin = add_command(
        sub, "plugin", help="agent-task plugins: the implementation of an agent task", add_arguments=_no_arguments, run=_plugin
    )
    psub = plugin.add_subparsers(dest="pcmd", required=True)
    new = psub.add_parser("new", help="create a plugin from the template")
    new.add_argument("directory")
    new.add_argument("--name", default="")
    lint = psub.add_parser("lint", help="check that a plugin's parts agree")
    lint.add_argument("paths", nargs="+")
    ren = psub.add_parser("render", help="write each coding agent's native hooks from hooks.toml")
    ren.add_argument("plugin")
    ren.add_argument("--agent", action="append", help="claude, codex, omp, opencode, pi (default: every renderer)")
    ren.add_argument("--check", action="store_true", help="only report files that are out of date")
    hook = psub.add_parser("hook", help="run a hook script on the input a coding agent's hook got, in Claude Code's shape")
    hook.add_argument("script", help="the hook script, relative to the plugin")
    hook.add_argument("--agent", required=True, choices=["codex"], help="the coding agent that runs the hook")
    hook.add_argument("--root", required=True, help="the plugin's directory")
    hook.add_argument("--tool", default="", help="the tool the hook is for, as hooks.toml names it (default: every tool)")
    hook.add_argument("--match", default="", help="run only when the command holds this text")

    call = add_command(sub, "call", help="agent-task call files", add_arguments=_no_arguments, run=_call)
    csub = call.add_subparsers(dest="ccmd", required=True)
    val = csub.add_parser("validate", help="check the output a call file names (a plugin's Stop hook)")
    val.add_argument("--call", default=None, help="the call file (default: $CONTRAAGENT_CALL)")

    recording = add_command(
        sub,
        "recording",
        help="recordings a replay plays (contraagent docs testing, Record once, replay in CI)",
        add_arguments=_no_arguments,
        run=_recording,
    )
    rsub = recording.add_subparsers(dest="rcmd", required=True)
    imp = rsub.add_parser(
        "import",
        help="write a recording of each task a run finished, from its run directory, as if the run had been recorded",
        epilog="exit status: 0 when every task the run finished was imported, 1 when one could not be (a missing or "
        "rewritten file, a file over the cap) or none was, or when the run directory cannot be read; a task that "
        "did not finish is listed, not imported",
    )
    imp.add_argument("run_dir", metavar="RUN_DIR", help="the run's directory (runs/<run-id>)")
    imp.add_argument("directory", metavar="DIR", help="the recordings directory to write into, as --record and --replay name it")
    imp.add_argument(
        "--record-max-file-mb",
        type=float,
        default=None,
        metavar="N",
        help="a task with a file larger than N MB is not imported (default 4), as a recording keeps it by hash only",
    )

    add_command(
        sub,
        "check",
        help="check a flow, its plugins and its routing without launching anything",
        add_arguments=_check_arguments,
        run=_flow_command,
        epilog="exit status: 0 when every check passes (warnings included), 1 when one fails or the flow's module "
        "cannot be loaded, 2 on a usage error (the flow's name, --kwargs, options)",
    )
    add_command(
        sub,
        "run",
        help="run a flow, as `check` names it, and report its tasks (for more control, call Pipeline.run from Python)",
        add_arguments=_run_arguments,
        run=_flow_command,
        epilog="exit status: 0 when the run is ok (RunReport.ok: no task and no flow call failed), 1 when it is not "
        "(in a stub run too: a task whose example fails its validators has failed), or when the run is refused "
        "before its first task (the config, the routing, a run id that holds a run, the preflight), "
        "2 on a usage error (the flow's name, --kwargs, options that do not go together)",
    )
    add_command(
        sub, "docs", help="the documentation installed with this version: the index, or one topic", add_arguments=_docs_arguments, run=_docs
    )
    return ap


def _no_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def _call(args) -> int:
    from contraagent._internal.contracts.calls import validate_call

    code, message = validate_call(args.call, sys.stdin.read() if not sys.stdin.isatty() else "")
    if message:
        print(message, file=sys.stderr)
    return code


def _recording(args) -> int:
    from contraagent._internal.execution.recording import MAX_FILE_MB, RecordingError
    from contraagent._internal.execution.recording_import import import_recording

    cap = args.record_max_file_mb if args.record_max_file_mb is not None else MAX_FILE_MB
    try:
        report = import_recording(args.run_dir, args.directory, max_file_mb=cap)
    except RecordingError as exc:
        print(f"✗ {exc}")
        return 1
    print(report)
    return 0 if report.ok else 1


def _docs_arguments(docs: argparse.ArgumentParser) -> None:
    docs.add_argument("topic", nargs="?", help="a topic the index lists (guide, tasks, ...)")
    docs.add_argument("--path", action="store_true", help="print where the documentation and its examples are installed")
    docs.add_argument(
        "--pointer",
        action="store_true",
        help="print a block for your coding agent's instruction file (AGENTS.md, CLAUDE.md) that points it at this documentation",
    )


def _check_arguments(chk: argparse.ArgumentParser) -> None:
    _flow_arguments(chk)
    chk.add_argument("--stub", action="store_true", help="the stub agent stands in for every coding agent (a config naming a custom one)")


def _run_arguments(run: argparse.ArgumentParser) -> None:
    _flow_arguments(run)
    run.add_argument("--run-id", default="", help="the run's id (default: the flow's name)")
    run.add_argument("--resume", action="store_true", help="continue the run: skip the tasks it already finished")
    add_runs_dir(run, "where run directories are written (default: runs)")
    run.add_argument(
        "--preflight",
        choices=("substitute", "stop", "off"),
        default=None,
        help="probe every route before the first task; a kind left with no route that answered runs on the first route "
        "that answered (substitute) or refuses the run (stop); off: no probe (default: [defaults] preflight, else off)",
    )
    run.add_argument(
        "--stub",
        action="store_true",
        help="a stub run: the stub agent plays every agent task and every Python task with its output's example "
        "(`examples` in the output's JSON Schema; where there is none, the smallest value the schema accepts); no model "
        "is called and no Python task's function runs, but those of --execute (run id: <flow>-stub). "
        "A task whose example fails a validator ends invalid_output at once, and the last line names those validators",
    )
    run.add_argument(
        "--execute",
        action="append",
        default=[],
        metavar="PATTERN",
        help="with --stub or --replay: run the functions of the Python task kinds PATTERN matches instead of playing "
        "them: a kind, or an fnmatch pattern of kinds ('*': every Python task, and only the agent tasks are played); "
        "repeatable",
    )
    run.add_argument(
        "--record",
        default=None,
        metavar="DIR",
        help="write each task attempt's recording to DIR: its outputs, the files its changes= patterns saw change, "
        "its transcript and its result",
    )
    run.add_argument(
        "--replay",
        default=None,
        metavar="DIR",
        help="a replay: play the recordings in DIR in place of every agent task's launch and every Python task's function "
        "(but the kinds of --execute); nothing is spent (run id: <flow>-replay). "
        "Not with --stub or --record",
    )
    run.add_argument(
        "--record-max-file-mb",
        type=float,
        default=None,
        metavar="N",
        help="with --record or --record-missing: keep a recorded file larger than N MB by its SHA-256 and size only "
        "(default 4); its task cannot be replayed",
    )
    run.add_argument(
        "--record-missing",
        action="store_true",
        help="with --replay: a task with no recording in DIR launches (or runs its function) as in any run, and its "
        "recording is written into DIR; this can spend tokens",
    )


def _docs(args) -> int:
    from contraagent._internal import docs

    try:
        if args.pointer:
            print(docs.POINTER, end="")
            return 0
        print(docs.DIR if args.path else docs.text(args.topic), end="\n" if args.path else "")
        return 0
    except docs.DocsError as exc:
        print(exc, file=sys.stderr)
        return 1


def _flow_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """What `check` and `run` take alike: the flow, its arguments, the config and overrides."""
    parser.add_argument("flow", help="the flow function: path/to/tasks.py:flow or package.module:flow")
    parser.add_argument("--config", default=None, help="the pipeline's TOML file (default: each task's declared defaults)")
    parser.add_argument("--kwargs", default="{}", help="the flow's keyword arguments, as a JSON object")
    parser.add_argument("--agent", default="", help="run every kind on this coding agent, with no failover hops (an override)")
    parser.add_argument("--model", default="", help="run every kind on this model, with no failover hops (an override)")
    return parser


def _spent(s: dict) -> str:
    """A run's time, cost and correction rounds, from its `RunReport.summary`."""
    spent = [f"{s.get('wall_s', 0):.1f}s"]
    spent += [f"${s['cost_usd']:.4f}"] if s.get("cost_usd") is not None else []
    spent += [f"{s['corrections']} correction round{'s' if s['corrections'] != 1 else ''}"] if s.get("corrections") else []
    return ", ".join(spent)


def _flow_command(args) -> int:
    import json

    from contraagent._internal.errors import ContraagentError
    from contraagent._internal.execution.run import RunExists
    from contraagent._internal.pipeline import Pipeline
    from contraagent._internal.pipeline.check import where
    from contraagent._internal.routing import Overrides

    try:
        split_spec(args.flow)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    try:
        kwargs = json.loads(args.kwargs)
        if not isinstance(kwargs, dict):
            raise ValueError("not a JSON object")
    except ValueError as exc:
        print(f"--kwargs: {exc}", file=sys.stderr)
        return 2
    try:
        flow = load_attr(args.flow)
        backends = None
        stub = None
        if args.cmd == "check" and args.stub:
            from contraagent._internal.testing import StubAgent

            backends = StubAgent().backends()
        elif args.cmd == "run" and args.stub:
            from contraagent._internal.testing import StubAgent, writes_example

            stub = StubAgent(default=writes_example(), execute=args.execute)
        record = getattr(args, "record", None)
        replay = getattr(args, "replay", None)
        if args.cmd == "run" and args.execute and not args.stub and replay is None:
            print("--execute: only with --stub or --replay", file=sys.stderr)
            return 2
        if args.cmd == "run" and args.record_missing and replay is None:
            print("--record-missing: only with --replay", file=sys.stderr)
            return 2
        if replay is not None and (args.stub or record is not None):
            print(f"--replay: not with {'--stub' if args.stub else '--record'}", file=sys.stderr)
            return 2
        overrides = Overrides(agent=args.agent, model=args.model)
        pipeline = Pipeline(
            args.config,
            runs_dir=getattr(args, "runs_dir", "runs"),
            backends=backends,
            overrides=overrides,
            stub=stub,
            preflight=getattr(args, "preflight", None),
            record=record,
            replay=replay,
            execute=args.execute if replay is not None else (),
            record_missing=bool(getattr(args, "record_missing", False)),
            record_max_file_mb=getattr(args, "record_max_file_mb", None),
        )
    except Exception as exc:  # the declarations themselves: a missing role, an unknown key, a bad config
        kind = "" if isinstance(exc, ContraagentError) else f"{type(exc).__name__}: "
        print(f"✗ {args.flow}\n  error: {where(exc)}{kind}{exc}\n  read: (contraagent docs tasks)")
        return 1
    if args.cmd == "check":
        report = pipeline.check(flow, **kwargs)
        print(report)
        return 0 if report.ok else 1
    setup_logging("%(asctime)s %(message)s", "%H:%M:%S")
    try:
        result = pipeline.run(flow, run_id=args.run_id or None, resume=args.resume, **kwargs)
    except RunExists as exc:  # in the command line's words, not the Python API's
        print(
            f"✗ {args.flow}\n  error: {Path(exc.run_dir).as_posix()} already holds a run ({exc.rows} journal rows): "
            "continue it with --resume, or start a new one with another --run-id"
        )
        return 1
    except ContraagentError as exc:  # refused before anything ran: routing, the preflight
        print(f"✗ {args.flow}\n  error: {exc}")
        return 1
    done = len(result.results) - len(result.failed) - len(result.deferred)
    spent = _spent(result.summary)
    if stub is not None:
        _print_created(result)
    later = f", {len(result.deferred)} deferred" if result.deferred else ""
    run_dir = Path(result.run_dir)
    print(f"{'✓' if result.ok else '✗'} {done}/{len(result.results)} tasks done{later} in {spent}; run in {run_dir.as_posix()}")
    for failed in result.failed:
        # A path in the run's directory as the run names it (`out/<kind>/<unit>.json`), as the log does.
        reason = failed.reason.replace(run_dir.resolve().as_posix() + "/", "").replace(run_dir.as_posix() + "/", "")
        print(f"  {failed.task.key}: {failed.stop} {reason[:300]}")
    for deferred in result.deferred:
        print(f"  {deferred.task.key}: deferred {deferred.reason[:300]}")
    for call in result.flow_errors:
        print(f"  flow call {call.id} ({call.function}): {type(call.error).__name__}: {str(call.error)[:300]}")
    if stub is not None and (note := _examples_refused(result, stub)):
        print(note)
    return 0 if result.ok else 1


def _examples_refused(result, stub) -> str:
    """In a stub run, the statement on the tasks whose example failed its checks: how
    many, the checks of each kind that refused it, and the next step. Empty when there are none."""
    import re

    checks: dict[str, list[str]] = {}
    count = 0
    for failed in result.failed:
        task = failed.task
        if failed.stop != "invalid_output" or (task.executor == "python" and not stub.plays(task.kind)):
            continue  # not the stub's output: a Python task kind it executes
        count += 1
        names = checks.setdefault(task.kind, [])
        for error in failed.round_errors[-1] if failed.round_errors else ():
            for name in re.findall(r"\[([^\]]+)\]", error)[:1]:  # `path: [validator] message`
                names += [name] if name not in names else []
    if not count:
        return ""
    refused = "; ".join(f"{kind}: {', '.join(names) or 'its checks'}" for kind, names in checks.items())
    tasks = "1 task" if count == 1 else f"{count} tasks"
    return (
        f"{tasks} failed checks on the examples the stub agent wrote ({refused}), so the tasks that need "
        f"{'its output' if count == 1 else 'their outputs'} did not run. Give each output model an example that "
        "passes its validators (contraagent docs testing, Stub run: the whole flow on examples, nothing called)"
    )


def _print_created(result) -> None:
    """The tasks a run's flow created, in the order it created them: `kind · unit`, how each
    ended, and the flow path that created it (its functions, the last one's line)."""
    from contraagent._internal.runs import layout
    from contraagent._internal.runs.files import read_rows

    rows = read_rows(result.run_dir / layout.PLAN)
    print(f"{len(rows)} task{'s' if len(rows) != 1 else ''} created:")
    for row in rows:
        res = result.results.get(row["key"])
        ended = res.stop if res is not None else "not run"
        frames = row.get("flow") or []
        where = " > ".join(f["function"].rsplit(".", 1)[-1] for f in frames)
        if frames:
            where += f" (line {frames[-1]['line']})"
        name = f"{row['kind']} · {row['unit']}" if row["unit"] else row["kind"]  # as the monitor names it
        print(f"  {name} | {ended}" + (f" | {where}" if where else ""))


def _plugin(args) -> int:
    from contraagent._internal.plugins import Plugin, PluginError, hooks, is_plugin, new_plugin

    if args.pcmd == "new":
        try:
            files = new_plugin(args.directory, args.name)
        except FileExistsError as exc:
            print(f"refusing to overwrite: {exc}", file=sys.stderr)
            return 1
        for f in files:
            print(f"  wrote {_shown(f)}")
        print(f"\nnext: write the procedure in {args.directory}/agents/worker.md, then `contraagent plugin lint {args.directory}`")
        return 0
    if args.pcmd == "hook":
        code, out, err = hooks.run_codex_hook(sys.stdin.read(), args.root, args.script, args.tool, args.match)
        sys.stdout.write(out)
        if err:
            print(err, file=sys.stderr)
        return code
    if args.pcmd == "lint":
        roots: list[Path] = []
        for p in map(Path, args.paths):
            roots += [p] if is_plugin(p) else sorted(d for d in p.glob("*") if is_plugin(d))
        if not roots:
            print("no plugin found (a directory with .claude-plugin/plugin.json)", file=sys.stderr)
            return 1
        bad = 0
        for r in roots:
            try:
                errs = Plugin.load(r).lint()
            except PluginError as exc:
                errs = [str(exc)]
            print(f"{'✗' if errs else '✓'} {r.as_posix()}")
            for e in errs:
                print(f"    {e}")
            bad += bool(errs)
        return 1 if bad else 0
    # render
    p = Plugin.load(args.plugin)
    errs = hooks.hook_errors(p.hooks)
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    if args.check:
        old = hooks.stale(p, args.agent)
        for rel in old:
            print(f"  stale: {rel}")
        return 1 if old else 0
    written, notes = hooks.write(p, args.agent)
    for f in written:
        print(f"  wrote {_shown(f)}")
    for n in notes:
        print(f"  note: {n}")
    print("up to date" if not written else "")
    return 0


def _shown(path: Path) -> str:
    """`path` relative to the working directory when it is under it, with `/` on every OS."""
    path = Path(path).resolve()
    return (path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
