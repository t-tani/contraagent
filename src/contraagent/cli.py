"""`contraagent` command line.

contraagent monitor [--runs-dir runs] [--port 8787]
contraagent monitor export --out site/stats [--runs 10]   # the monitor as files, served with no server
contraagent plugin new plugins/summarize [--name N]
contraagent plugin lint plugins          # a plugin, or a directory of plugins
contraagent plugin render <plugin>       # hooks.toml -> each coding agent's native hooks
contraagent call validate [--call PATH]  # what a plugin's Stop hook runs (default: $CONTRAAGENT_CALL)
contraagent check tasks.py:docs --config pipeline.toml --kwargs '{"units": ["alpha"]}'
                                         # a flow, checked without launching anything
contraagent run tasks.py:docs --config pipeline.toml --kwargs '{"units": ["alpha"]}' [--run-id ID] [--resume]
                                         [--preflight substitute|stop|off]
                                         # the same flow, run (exit 1 when a task or the flow failed)
contraagent run tasks.py:docs --stub [--execute KIND]
                                         # a stub run: the stub agent plays every task with the smallest
                                         # output, and the tasks the flow created are listed
contraagent docs [TOPIC] [--path]        # the documentation installed with the package
contraagent docs --pointer >> AGENTS.md  # point a project's coding agent at it
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["monitor"]:
        # Handed over whole: argparse's REMAINDER drops a leading `--option`
        # (`contraagent monitor --runs-dir x` was "unrecognized arguments").
        from contraagent.monitor.server import main as monitor_main

        return monitor_main(argv[1:])
    if argv[:1] == ["relay"]:
        from contraagent.hub.relay import main as relay_main

        return relay_main(argv[1:])
    if argv[:1] == ["hub"]:
        from contraagent.hub.server import main as hub_main

        return hub_main(argv[1:])
    # Output piped into `head` ends quietly, as a command line tool's should.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(prog="contraagent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("monitor", help="live web monitor for runs (see `contraagent monitor --help`)")
    sub.add_parser("relay", help="ship this host's runs to a hub (see `contraagent relay --help`)")
    sub.add_parser("hub", help="receive every host's runs and serve their monitor (see `contraagent hub --help`)")

    plugin = sub.add_parser("plugin", help="agent-task plugins: the implementation of an agent task")
    psub = plugin.add_subparsers(dest="pcmd", required=True)
    new = psub.add_parser("new", help="create a plugin from the template")
    new.add_argument("directory")
    new.add_argument("--name", default="")
    lint = psub.add_parser("lint", help="check that a plugin's parts agree")
    lint.add_argument("paths", nargs="+")
    ren = psub.add_parser("render", help="write each coding agent's native hooks from hooks.toml")
    ren.add_argument("plugin")
    ren.add_argument("--agent", action="append", help="claude, omp (default: every renderer)")
    ren.add_argument("--check", action="store_true", help="only report files that are out of date")

    call = sub.add_parser("call", help="agent-task call files")
    csub = call.add_subparsers(dest="ccmd", required=True)
    val = csub.add_parser("validate", help="check the output a call file names (a plugin's Stop hook)")
    val.add_argument("--call", default=None, help="the call file (default: $CONTRAAGENT_CALL)")

    chk = _flow_arguments(sub.add_parser("check", help="check a flow, its plugins and its routing without launching anything"))
    chk.add_argument("--stub", action="store_true", help="the stub agent stands in for every coding agent (a config naming a custom one)")
    run = _flow_arguments(
        sub.add_parser(
            "run",
            help="run a flow, as `check` names it, and report its tasks (for more control, call Pipeline.run from Python)",
        )
    )
    run.add_argument("--run-id", default="", help="the run's id (default: the flow's name)")
    run.add_argument("--resume", action="store_true", help="continue the run: skip the tasks it already finished")
    run.add_argument("--runs-dir", default="runs", help="where run directories are written (default: runs)")
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
        help="a stub run: the stub agent plays every agent task and every Python task with the smallest output its schema "
        "accepts; no model is called and no Python task's function runs (run id: <flow>-stub)",
    )
    run.add_argument(
        "--execute",
        action="append",
        default=[],
        metavar="KIND",
        help="with --stub: run the function of this Python task kind instead of playing it (repeatable)",
    )
    run.add_argument(
        "--record",
        default=None,
        metavar="DIR",
        help="write each agent task attempt's recording to DIR: its outputs, the files its changes= patterns saw change, "
        "its transcript and its result",
    )
    run.add_argument(
        "--replay",
        default=None,
        metavar="DIR",
        help="a replay: play the recordings in DIR in place of every agent task's launch; Python tasks run their functions, "
        "nothing is spent (run id: <flow>-replay). Not with --stub or --record",
    )

    docs = sub.add_parser("docs", help="the documentation installed with this version: the index, or one topic")
    docs.add_argument("topic", nargs="?", help="a topic the index lists (guide, tasks, ...)")
    docs.add_argument("--path", action="store_true", help="print where the documentation and its examples are installed")
    docs.add_argument(
        "--pointer",
        action="store_true",
        help="print a block for your coding agent's instruction file (AGENTS.md, CLAUDE.md) that points it at this documentation",
    )
    args = ap.parse_args(argv)

    if args.cmd == "docs":
        return _docs(args)
    if args.cmd in ("check", "run"):
        return _flow_command(args)
    if args.cmd == "call":
        from contraagent.calls import validate_call

        code, message = validate_call(args.call, sys.stdin.read() if not sys.stdin.isatty() else "")
        if message:
            print(message, file=sys.stderr)
        return code
    return _plugin(args)


def _docs(args) -> int:
    from contraagent import docs

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


def _flow_command(args) -> int:
    import importlib
    import json
    import logging

    from contraagent.errors import ContraagentError
    from contraagent.pipeline import Pipeline
    from contraagent.pipeline.check import where
    from contraagent.routing import Overrides

    target, _, name = args.flow.rpartition(":")
    if not target or not name:
        print(f"{args.flow}: expected path/to/tasks.py:flow or package.module:flow", file=sys.stderr)
        return 2
    try:
        kwargs = json.loads(args.kwargs)
        if not isinstance(kwargs, dict):
            raise ValueError("not a JSON object")
    except ValueError as exc:
        print(f"--kwargs: {exc}", file=sys.stderr)
        return 2
    if target.endswith(".py"):
        # Imported by its own name with its directory on sys.path: how the
        # in-session hook imports the output models it defines.
        path = Path(target).resolve()
        sys.path.insert(0, str(path.parent))
        target = path.stem
    sys.path.insert(0, str(Path.cwd()))
    try:
        flow = getattr(importlib.import_module(target), name)
        backends = None
        stub = None
        if args.cmd == "check" and args.stub:
            from contraagent.testing import StubAgent

            backends = StubAgent().backends()
        elif args.cmd == "run" and args.stub:
            from contraagent.testing import StubAgent, writes_smallest

            stub = StubAgent(default=writes_smallest(), execute=args.execute)
        elif args.cmd == "run" and args.execute:
            print("--execute: only with --stub", file=sys.stderr)
            return 2
        record = getattr(args, "record", None)
        replay = getattr(args, "replay", None)
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
        )
    except Exception as exc:  # the declarations themselves: a missing role, an unknown key, a bad config
        kind = "" if isinstance(exc, ContraagentError) else f"{type(exc).__name__}: "
        print(f"✗ {args.flow}\n  error: {where(exc)}{kind}{exc}\n  read: `contraagent docs tasks`")
        return 1
    if args.cmd == "check":
        report = pipeline.check(flow, **kwargs)
        print(report)
        return 0 if report.ok else 1
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    try:
        result = pipeline.run(flow, run_id=args.run_id or None, resume=args.resume, **kwargs)
    except ContraagentError as exc:  # refused before anything ran: routing, a run id that holds a run, the preflight
        print(f"✗ {args.flow}\n  error: {exc}")
        return 1
    done = len(result.results) - len(result.failed)
    s = result.summary
    spent = [f"{s.get('wall_s', 0):.1f}s"]
    spent += [f"${s['cost_usd']:.4f}"] if s.get("cost_usd") is not None else []
    spent += [f"{s['fixups']} fix-up{'s' if s['fixups'] != 1 else ''}"] if s.get("fixups") else []
    if stub is not None:
        _print_created(result)
    print(f"{'✓' if result.ok else '✗'} {done}/{len(result.results)} tasks done in {', '.join(spent)}; run in {result.run_dir}")
    for failed in result.failed:
        print(f"  {failed.task.key}: {failed.stop} {failed.reason[:300]}")
    for call in result.flow_errors:
        print(f"  flow call {call.id} ({call.function}): {type(call.error).__name__}: {str(call.error)[:300]}")
    return 0 if result.ok else 1


def _print_created(result) -> None:
    """The tasks a run's flow created, in the order it created them: `kind · unit`, how each
    ended, and the flow path that created it (its functions, the last one's line)."""
    import json

    from contraagent import rundir

    try:
        rows = [json.loads(line) for line in (result.run_dir / rundir.PLAN).read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        rows = []
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
    from contraagent.plugins import Plugin, PluginError, hooks, is_plugin, new_plugin

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
            print(f"{'✗' if errs else '✓'} {r}")
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


def _shown(path: Path) -> Path:
    """`path` relative to the working directory when it is under it."""
    path = Path(path).resolve()
    return path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path


if __name__ == "__main__":
    raise SystemExit(main())
