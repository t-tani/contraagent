"""What the commands of `contraagent` share: how a command is added to the tree, the option
groups several commands take, loading `path/to/file.py:attr`, logging, and the errors a
command reports.

`contraagent._internal.cli` holds the tree; a command's module (`monitor.server`, `monitor.export`,
`hub.server`, `hub.relay`) exposes `add_arguments(parser)` and `run(args) -> int` and
uses the groups below. This module imports nothing else from the package, so any layer
can use it.
"""

from __future__ import annotations

import argparse
import errno
import importlib
import importlib.util
import logging
import re
import signal
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any


class UsageError(Exception):
    """Arguments the command cannot take together: reported with the command's usage, exit 2."""


class CommandError(Exception):
    """What stops a command before it does its work (a file it cannot read, a bad spec):
    reported as `<command>: <message>`, exit 2."""


class MissingExtra(ModuleNotFoundError):
    """A module of an optional extra is not installed (`monitor.server.require_extra`);
    a command reports it as a `CommandError`."""


def add_command(
    subparsers: Any,
    name: str,
    *,
    help: str,
    add_arguments: Callable[[argparse.ArgumentParser], None],
    run: Callable[[argparse.Namespace], int],
    long_running: bool = False,
    epilog: str | None = None,
) -> argparse.ArgumentParser:
    """Add the command `name` to `subparsers`: its arguments, and `run` as what it does.
    `long_running`: it runs servers or agents (a server, a relay, a run), so a closed pipe,
    to its output or to an agent's input, is an error it handles (BrokenPipeError), never
    the end of the process by SIGPIPE. `epilog`: printed after its options (its exit
    status)."""
    parser = subparsers.add_parser(name, help=help, epilog=epilog)
    add_arguments(parser)
    parser.set_defaults(run=run, parser=parser, long_running=long_running)
    return parser


def add_runs_dir(parser: argparse.ArgumentParser, help: str = "directory holding runs/<run-id>/ (default: ./runs)") -> None:
    parser.add_argument("--runs-dir", default="runs", help=help)


#: The monitor's extensions: the options that name a pipeline's own code, and what each is.
EXTENSIONS = {
    "panels": "the pipeline's own views: a dict of name -> Panel (or a callable), as path/to/views.py:PANELS or package.module:PANELS",
    "groups": 'the plan\'s columns and the trends\' groups: a list of {"id", "label", "kinds"}, '
    "as path/to/views.py:GROUPS or package.module:GROUPS",
    "task_detail": "fn(run, key, rows) -> dict merged into each task's detail, as path/to/views.py:detail or package.module:detail",
    "apps": "the pipeline's own pages: a dict of name -> ASGI app, each served under apps/<name>/ of the monitor, "
    "as path/to/views.py:APPS or package.module:APPS",
}


def add_extensions(parser: argparse.ArgumentParser) -> None:
    """`--panels`, `--groups`, `--task-detail`, `--apps`: what `Monitor(panels=, groups=, task_detail=, apps=)` takes."""
    for name, help in EXTENSIONS.items():
        parser.add_argument("--" + name.replace("_", "-"), default=None, metavar="MODULE:ATTR", help=help)


def load_extensions(args: argparse.Namespace) -> dict[str, Any]:
    """What the extension options name, loaded (`load_attr`), as `Monitor`'s keyword arguments."""
    loaded: dict[str, Any] = {}
    for name in EXTENSIONS:
        spec = getattr(args, name)
        if not spec:
            continue
        try:
            loaded[name] = load_attr(spec)
        except Exception as exc:  # an import that fails is the user's to fix: say which
            raise CommandError(f"--{name.replace('_', '-')} {spec}: {type(exc).__name__}: {exc}") from None
    return loaded


def add_http(parser: argparse.ArgumentParser, *, port: int) -> None:
    """Where a server listens, which `Host` names and origins it answers, and the path a proxy serves it under."""
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=port)
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="NAME",
        help="also answer monitor requests addressed to this host name (default: localhost, 127.0.0.1, [::1] and the --host address)",
    )
    parser.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="let a page from this origin read the monitor API, e.g. http://localhost:5173 for a UI dev server",
    )
    parser.add_argument(
        "--base-path",
        type=_base_path_option,
        default="",
        metavar="PATH",
        help="the path a reverse proxy serves the monitor under, e.g. /monitor: the page names it in every URL it reads; "
        "the proxy takes it off before it passes a request on (default: none, the monitor is at /)",
    )


#: One segment of a base path: unreserved characters of a URL, or a percent-encoded byte.
_SEGMENT = re.compile(r"(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2})+")


def base_path(value: str) -> str:
    """`value` as the path a reverse proxy serves the monitor under: `/monitor` (a
    trailing `/` dropped), or '' for none (`''` or `/`). `ValueError` names what is wrong
    with any other value: a scheme or host, a missing leading `/`, an empty, `.` or `..`
    segment, or a character beside letters, digits, `.`, `_`, `~`, `-` and `%XX`."""
    path = value.rstrip("/")
    if not path:
        return ""
    if "://" in value or value.startswith("//"):
        raise ValueError(f"{value!r}: a path such as /monitor, with no scheme or host")
    if not path.startswith("/"):
        raise ValueError(f"{value!r}: a path starts with /, such as /monitor")
    for segment in path[1:].split("/"):
        if segment in ("", ".", ".."):
            raise ValueError(f"{value!r}: an empty, . or .. segment")
        if not _SEGMENT.fullmatch(segment):
            raise ValueError(f"{value!r}: only letters, digits, . _ ~ - and %XX between the / of a path")
    return path


def _base_path_option(value: str) -> str:
    try:
        return base_path(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def bind(host: str, port: int) -> socket.socket:
    """A TCP socket bound to `host`:`port` (`OSError` when it cannot be), for `serve_on`:
    a server announces its address only once it holds it."""
    sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET)
    if sys.platform == "win32":  # SO_REUSEADDR there lets a second server take the port too
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise
    return sock


def bind_option(host: str, port: int) -> socket.socket:
    """`bind` for a command given `--host` and `--port`: a failure is a `CommandError`
    naming the option to change."""
    try:
        return bind(host, port)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise CommandError(f"port {port} on {host} is already in use (--port)") from None
        raise CommandError(f"cannot listen on {host} port {port} (--host, --port): {exc.strerror or exc}") from None


def serve_on(app: Any, sock: socket.socket) -> None:
    """Serve the ASGI `app` on the bound `sock` (uvicorn) until stopped."""
    import uvicorn

    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


def address(sock: socket.socket) -> str:
    """`http://host:port` of a bound socket (the port it got when it asked for 0)."""
    host, port = sock.getsockname()[:2]
    return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"


def add_openapi(parser: argparse.ArgumentParser, document: str) -> None:
    parser.add_argument(
        "--openapi",
        nargs="?",
        const="-",
        metavar="PATH",
        help=f"write the {document} to PATH (default: stdout) and exit",
    )


def write_openapi(document: str, dest: str) -> None:
    """`document` written to the file `dest`, or to stdout for `-` (piped into `head`, it ends quietly)."""
    if dest == "-":
        if sys.platform != "win32":  # Windows has no SIGPIPE
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        sys.stdout.write(document)
    else:
        Path(dest).write_text(document, encoding="utf-8", newline="\n")


def setup_logging(format: str = "%(message)s", datefmt: str | None = None) -> None:
    """INFO and above to stderr in `format`, unless the program set logging up itself."""
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format=format, datefmt=datefmt)


def split_spec(spec: str) -> tuple[str, str]:
    """`path/to/file.py:attr` or `package.module:attr` as (file or module, attr)."""
    target, _, name = spec.rpartition(":")
    if not target or not name:
        raise ValueError(f"{spec}: expected path/to/file.py:attr or package.module:attr")
    return target, name


#: The modules `load_attr` put in `sys.modules`, by name: the names it may give to a file again.
_loaded: dict[str, ModuleType] = {}


def _file_of(module: Any) -> Path | None:
    file = getattr(module, "__file__", None)
    return Path(file).resolve() if isinstance(file, str) else None


def load_attr(spec: str) -> Any:
    """What `path/to/file.py:attr` or `package.module:attr` names. The working directory is
    on `sys.path`. A file is loaded from its path, anew, under its own name (`sys.modules`),
    with its directory on `sys.path` first, as `python path/to/file.py` puts it there: it
    imports its neighbours, at load time and later (a task's function may import one when
    it runs), and a hook in the session imports the output models it defines by the same
    name. A file loaded here before under the same name gives the name up to it. A name
    that `sys.modules` gives to any other module (the standard library's `queue`, a
    module of an installed package) raises ImportError: replacing it would change that
    module for every importer. A module is imported."""
    target, name = split_spec(spec)
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    if not target.endswith(".py"):
        return getattr(importlib.import_module(target), name)
    path = Path(target).resolve()
    if not path.is_file():
        raise OSError(f"{spec}: no file {path}")
    taken = sys.modules.get(path.stem)
    if taken is not None and taken is not _loaded.get(path.stem):
        where = _file_of(taken) or "built into Python"
        raise ImportError(f"{spec}: the module name {path.stem!r} is already {where}; rename {path.name}")
    if str(path.parent) in sys.path:
        sys.path.remove(str(path.parent))
    sys.path.insert(0, str(path.parent))
    found = importlib.util.spec_from_file_location(path.stem, path)
    if found is None or found.loader is None:
        raise ImportError(f"{spec}: cannot load {path}")
    module = importlib.util.module_from_spec(found)
    sys.modules[path.stem] = _loaded[path.stem] = module
    try:
        found.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(path.stem, None)
        _loaded.pop(path.stem, None)
        raise
    return getattr(module, name)
