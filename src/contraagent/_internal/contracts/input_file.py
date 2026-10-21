"""`InputFile`: a file a task is given as a param, by its path and the hash of its content.

A large input (a long text another task wrote, a data file) is not copied into the
params: the task is given an `InputFile`, which holds a path. At the task call,
contraagent takes the SHA-256 of the file's content (`bind`), and the params hold
`{"path": ..., "sha256": ...}`, or `{"root": ..., "path": ..., "sha256": ...}` for a file
of an input root: the fingerprint holds the hash, so a file with other content at the
same path runs the task again on a resume. When the task is about to start, the file must
still have that content (`changed`), or the task is refused (`invalid_input`).

The path is one of the task's working directory (the `cwd` of its call options, else
`Pipeline(cwd=)`), held relative to it, or one of an input root, held relative to the
root with the root's name: a root the run names (`Pipeline(input_roots=)`), or `out`, the
run's `out/` directory, where the tasks' output files are. An output file of the run given
by its path is held as a file of `out`. A path that leads outside all of them, itself or
through a symbolic link, raises `ValueError` at the task call, and so does an absolute path
under a root the run names, which is given with its root; a relative path that climbs out
with `..` raises where the `InputFile` is made.

The call file an agent reads holds each file of an input root by its absolute path
(`with_absolute_paths`), so the agent, its validators and the stop hook need no root.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

from contraagent._internal.dispatch.python_task import InvalidInput

#: The key of pydantic's serialization context that holds a task call's input files,
#: hashed (`bind`): the path an `InputFile` holds -> its `Bound`.
BINDINGS = "contraagent.input_files"
#: The key of pydantic's validation context that holds the directories the relative paths
#: of input files' JSON are under, for a Python task's arguments: by input root name, and
#: the working directory under "".
ROOTS = "contraagent.input_roots"
#: The input root every run has: its `out/` directory, where the tasks' output files are.
OUT = "out"
#: What an input root's name is.
ROOT_NAME = re.compile(r"[a-z][a-z0-9_-]*")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEYS = ({"path", "sha256"}, {"root", "path", "sha256"})

_DESCRIPTION = (
    "A file you are given by its path, not by its content: read it with your tools. It has this content as long as the task runs."
)


class InputFile:
    """A file a task is given as a param: its path, and the SHA-256 of its content taken
    at the task call. A large input goes to a task as one (a task's output,
    `pending.input_file()` once the flow awaited it; a file on disk,
    `InputFile("in/spec.md")`; a file of an input root, `InputFile("2026/x.csv", root="data")`)
    instead of being copied into its params.

    It is a field of an agent task's params model (`note: InputFile = Field(description=...)`)
    or a Python task's parameter (`def count(note: InputFile)`). The params hold
    `{"path": ..., "sha256": ...}`, the path relative to the task's working directory
    (the `cwd` of its call options, else `Pipeline(cwd=)`), or, for a file of an input root,
    `{"root": ..., "path": ..., "sha256": ...}`, the path relative to the root. The
    fingerprint holds the root, the path and the hash: a file with other content runs the
    task again on a resume, and so does the same content at another path, but not the same
    root moved to another directory. The JSON Schema of the params model tells the agent to
    read the file with its tools, and the call file it reads holds a root's file by its
    absolute path.

    `root` names an input root: one of `Pipeline(input_roots=)` (`contraagent run
    --input-root NAME=DIR`), or `out`, the run's `out/` directory, of which an output file
    of the run given by its path is too. Without it, the path is a file of the task's
    working directory, relative to it unless absolute. A path that climbs out with `..`, an
    absolute path with a root, or a root name that is not lowercase letters, digits, `_`
    and `-` starting with a letter, raises `ValueError` here. At the task call, `ValueError`
    for a root the run does not have, a path that leads outside its directory, itself or
    through a symbolic link, one that names no file, and an absolute path under a root the
    run names (give it with its root). When the task is about to start,
    the file must still have the content it had at the call, or the task is refused
    (`invalid_input`). A Python task is given an `InputFile` whose `path` is absolute, whose
    `root` is the one it was given with, and whose `sha256` is the hash taken at the call;
    `read_bytes` and `read_text` check the content against it."""

    __slots__ = ("_path", "_root", "_sha256")

    _path: Path
    _root: str | None
    _sha256: str | None

    def __init__(self, path: str | os.PathLike[str], root: str | None = None) -> None:
        self._root = _checked_root(root)
        self._path = _checked_path(path, self._root)
        self._sha256 = None

    @classmethod
    def _recorded(cls, path: str | os.PathLike[str], sha256: str, root: str | None = None) -> InputFile:
        """An input file as a task call recorded it: its path and the hash taken then; an
        absolute path with a root is one made absolute under it (a Python task's)."""
        made = object.__new__(cls)
        made._root = _checked_root(root)
        made._path = Path(path) if root is not None and Path(path).is_absolute() else _checked_path(path, made._root)
        made._sha256 = sha256
        return made

    @property
    def path(self) -> Path:
        """The path: as it was given, relative to its root or to the working directory
        unless absolute; in a Python task, absolute."""
        return self._path

    @property
    def root(self) -> str | None:
        """The name of the input root the path is under; None for a file of the working
        directory."""
        return self._root

    @property
    def sha256(self) -> str | None:
        """The SHA-256 of the content, in hex, taken at the task call that gave it; None
        for one made in the flow, which no task call has hashed."""
        return self._sha256

    def read_bytes(self) -> bytes:
        """The file's content. With a hash (`sha256`), content that does not match it
        raises `ValueError`: the file changed after the task call. In a Python task this
        refuses the task (`invalid_input`)."""
        data = self._path.read_bytes()
        if self._sha256 is not None and (now := hashlib.sha256(data).hexdigest()) != self._sha256:
            raise InvalidInput(f"input file {self._path.as_posix()} changed after the task call: {_changed(self._sha256, now)}")
        return data

    def read_text(self, encoding: str = "utf-8") -> str:
        """The file's content as text (`read_bytes`, decoded)."""
        return self.read_bytes().decode(encoding)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InputFile):
            return NotImplemented
        return (self._root, self._path, self._sha256) == (other._root, other._path, other._sha256)

    def __hash__(self) -> int:
        return hash((self._root, self._path, self._sha256))

    def __repr__(self) -> str:
        root = f", root={self._root!r}" if self._root is not None else ""
        hashed = f", sha256={self._sha256[:12]}..." if self._sha256 is not None else ""
        return f"InputFile({self._path.as_posix()!r}{root}{hashed})"

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler, /) -> CoreSchema:
        """Validated from an `InputFile`, or from its JSON (`{"path", "sha256"}`, with `root`
        for a file of an input root); in JSON, that object (`bind`)."""
        return core_schema.with_info_plain_validator_function(
            _validate,
            serialization=core_schema.plain_serializer_function_ser_schema(_serialize, info_arg=True, when_used="json"),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: CoreSchema, handler: GetJsonSchemaHandler, /) -> JsonSchemaValue:
        return {
            "type": "object",
            "title": "InputFile",
            "description": _DESCRIPTION,
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file's path, relative to your working directory unless it is absolute. "
                    "Read the file with your tools.",
                },
                "sha256": {
                    "type": "string",
                    "description": "The SHA-256 of the file's content, in hex, taken when the task was called.",
                },
            },
            "required": ["path", "sha256"],
            "additionalProperties": False,
        }


@dataclass(frozen=True)
class Bound:
    """An input file as a task call hashed it (`bind`)."""

    #: The path its JSON holds: relative to its input root, or to the working directory.
    shown: str
    #: The path, absolute, as given (a symbolic link in it not followed): what is hashed again when the task starts.
    path: Path
    #: The file it names, every symbolic link followed.
    real: Path
    sha256: str
    #: The name of its input root; None for a file of the working directory.
    root: str | None = None

    def json(self) -> dict[str, str]:
        if self.root is None:
            return {"path": self.shown, "sha256": self.sha256}
        return {"root": self.root, "path": self.shown, "sha256": self.sha256}

    @property
    def named(self) -> str:
        """The file as a message names it: `out/<path>` for an output file of the run, `<path>
        of input root <name>` for a file of another root, else its path."""
        if self.root is None:
            return self.shown
        return f"{OUT}/{self.shown}" if self.root == OUT else f"{self.shown} of input root {self.root}"


def bind(file: InputFile, cwd: Path, roots: Mapping[str, Path]) -> Bound:
    """`file` at a task call, its content hashed: a file of its input root (`roots`, by name,
    `out` among them), checked to be under the root's directory both as written and with
    every symbolic link followed; else a file of `cwd` or of the `out` root, made absolute
    under `cwd`, checked to be under one of them both ways, and held as a file of `out` when
    it is under it as written. ValueError for a root not in `roots`, a file outside, an
    absolute path under a root other than `out` given with no root, or one that names no
    file."""
    cwd = Path(os.path.abspath(cwd))
    dirs = {name: Path(os.path.abspath(d)) for name, d in roots.items()}
    given = file.path
    if file.root is not None:
        base = dirs.get(file.root)
        if base is None:
            raise ValueError(
                f"input file {given.as_posix()} names input root {file.root!r}, which this run does not have "
                f"(its input roots: {', '.join(sorted(dirs)) or 'none'}); name it in Pipeline(input_roots=) or --input-root NAME=DIR"
            )
        path = Path(os.path.normpath(given if given.is_absolute() else base / given))
        if not path.is_relative_to(base):
            raise ValueError(f"input file {given.as_posix()} is outside input root {file.root} ({base.as_posix()})")
        rel = path.relative_to(base).as_posix()
        return _hashed(path, rel, [base.resolve()], f"input root {file.root} ({base.as_posix()})", file.root)
    path = Path(os.path.normpath(given if given.is_absolute() else cwd / given))
    shown = given.as_posix()
    out = dirs.get(OUT)
    outs = [out, out.resolve()] if out is not None else []
    if given.is_absolute() and not _under(path, outs):
        for name, base in dirs.items():
            for d in (base, base.resolve()):
                if name != OUT and path.is_relative_to(d):
                    rel = path.relative_to(d).as_posix()
                    raise ValueError(
                        f"input file {shown} is under input root {name} ({base.as_posix()}); give it as InputFile({rel!r}, root={name!r})"
                    )
    if not _under(path, [cwd, cwd.resolve(), *outs]):
        raise ValueError(
            f"input file {shown} is outside the working directory {cwd.as_posix()}; give a file inside it, "
            "or one of an input root as InputFile(path, root=)"
        )
    allowed = [cwd.resolve(), *outs[1:]]
    for d in outs:
        if path.is_relative_to(d):  # an output file of the run: a file of `out`, wherever the run directory is
            return _hashed(path, path.relative_to(d).as_posix(), allowed, f"the working directory {cwd.as_posix()}", OUT, shown)
    return _hashed(path, _shown(path, cwd), allowed, f"the working directory {cwd.as_posix()}", None, shown)


def _hashed(path: Path, shown: str, allowed: Sequence[Path], where: str, root: str | None, given: str = "") -> Bound:
    """The `Bound` of `path`, which must name a file under `allowed` with every symbolic link
    followed; ValueError naming `given` (default: `shown`) and `where` it must be."""
    given = given or shown
    try:
        real = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError(f"input file {given} does not exist; a task is given a file that is there at its call") from None
    if not _under(real, allowed):
        raise ValueError(f"input file {given} is a symbolic link to {real.as_posix()}, outside {where}; give a file inside it")
    if not real.is_file():
        raise ValueError(f"input file {given} is not a file")
    digest = sha256_of(real)
    if digest is None:
        raise ValueError(f"input file {given} cannot be read")
    return Bound(shown=shown, path=path, real=real, sha256=digest, root=root)


def changed(bound: Bound) -> str:
    """Why the file a task call hashed no longer has that content, as the task is about to
    start; empty when it has."""
    now = sha256_of(bound.path)
    if now is None:
        return f"input file {bound.named} is gone; it was given to the task call with sha256 {bound.sha256[:12]}"
    if now != bound.sha256:
        return f"input file {bound.named} changed after the task call: {_changed(bound.sha256, now)}"
    return ""


def checked_roots(given: Mapping[str, str | os.PathLike[str]] | None, cwd: Path, where: str) -> dict[str, Path]:
    """The input roots a run names, by name, each directory absolute under `cwd` (symbolic
    links not followed, as `Pipeline(cwd=)`). ValueError for a name that is not lowercase
    letters, digits, `_` and `-` starting with a letter, or is `out` (the run's own); TypeError
    for a value that is not a path."""
    out: dict[str, Path] = {}
    for name, directory in (given or {}).items():
        if not isinstance(name, str) or not ROOT_NAME.fullmatch(name):
            raise ValueError(f"{where}: input root name {name!r} is not lowercase letters, digits, _ and - starting with a letter")
        if name == OUT:
            raise ValueError(f"{where}: input root name {OUT!r} is the run's own out/ directory; give the root another name")
        try:
            text = os.fspath(directory)
        except TypeError:
            raise TypeError(f"{where}: input root {name} is a {type(directory).__name__}, not a path") from None
        if not isinstance(text, str) or not text:
            raise TypeError(f"{where}: input root {name} is {directory!r}, not a path")
        out[name] = Path(os.path.abspath(Path(cwd) / text))
    return out


def missing_roots(roots: Mapping[str, Path]) -> list[str]:
    """Each input root whose directory is not a directory, as a problem."""
    return [f"input root {name} is {d.as_posix()}, which is not a directory" for name, d in roots.items() if not d.is_dir()]


def sha256_of(path: Path) -> str | None:
    """The SHA-256 of a file's content, in hex, read in blocks; None when it cannot be read."""
    try:
        with path.open("rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except OSError:
        return None


def _changed(then: str, now: str) -> str:
    return f"sha256 {then[:12]} at the call, {now[:12]} now; the task is given the content the file had at its call"


def _checked_root(root: Any) -> str | None:
    if root is None:
        return None
    if not isinstance(root, str) or not ROOT_NAME.fullmatch(root):
        raise ValueError(
            f"InputFile: root {root!r} is not an input root's name: lowercase letters, digits, _ and -, starting with a letter"
        )
    return root


def _checked_path(path: Any, root: str | None = None) -> Path:
    try:
        text = os.fspath(path)
    except TypeError:
        raise TypeError(f"InputFile takes a path (a str or a PathLike), not {type(path).__name__}") from None
    if not isinstance(text, str):
        raise TypeError(f"InputFile takes a path as text, not {type(text).__name__}")
    if not text:
        raise ValueError("InputFile takes a path, not an empty string")
    made = Path(text)
    within = "the working directory" if root is None else f"input root {root}"
    if root is not None and (made.is_absolute() or made.anchor):
        raise ValueError(f"input file {made.as_posix()} of input root {root} is absolute; give its path relative to the root")
    if not made.is_absolute() and (os.path.normpath(text).split(os.sep)[0] == os.pardir or made.anchor):
        raise ValueError(f"input file {made.as_posix()} climbs out of {within} with ..; give a file inside it")
    return made


def _under(path: PurePath, roots: Sequence[PurePath]) -> bool:
    return any(path.is_relative_to(root) for root in roots)


def _shown(path: Path, cwd: Path) -> str:
    """`path` relative to `cwd` when it is under it, as written or with `cwd`'s symbolic
    links followed; else absolute."""
    for root in (cwd, cwd.resolve()):
        if path.is_relative_to(root):
            return path.relative_to(root).as_posix()
    return path.as_posix()


def _validate(value: Any, info: core_schema.ValidationInfo) -> InputFile:
    if isinstance(value, InputFile):
        return value
    if _is_file_json(value) and (value.get("root") is None or ROOT_NAME.fullmatch(value["root"])) and value["path"]:
        path, sha256, root = value["path"], value["sha256"], value.get("root")
        dirs = info.context.get(ROOTS) if isinstance(info.context, dict) else None
        if dirs is not None:
            base = dirs.get(root or "")
            if base is None:
                raise ValueError(f"input file {path} names input root {root!r}, which this run does not have")
            if not Path(path).is_absolute():
                path = Path(base) / path
        return InputFile._recorded(path, sha256, root)
    raise ValueError(
        'an input file is InputFile(path) or InputFile(path, root=), or the JSON of one: {"path": "...", "sha256": "<64 hex digits>"}, '
        'with "root" for a file of an input root'
    )


def _serialize(file: InputFile, info: core_schema.SerializationInfo) -> dict[str, str]:
    """The JSON of `file`: in a task call, as the call hashed it (`BINDINGS`); else its root,
    its path and its hash, taken now when no task call has."""
    bindings = info.context.get(BINDINGS) if isinstance(info.context, dict) else None
    if bindings is not None:
        bound = bindings.get((file.root, file.path))
        if bound is None:
            raise ValueError(f"input file {file.path.as_posix()} was not hashed at the task call")
        return bound.json()
    digest = file.sha256 or sha256_of(file.path)
    if digest is None:
        raise ValueError(f"input file {file.path.as_posix()} cannot be read")
    rooted = {"root": file.root} if file.root is not None else {}
    return {**rooted, "path": file.path.as_posix(), "sha256": digest}


def _is_file_json(value: Any) -> bool:
    """`value` is an input file's JSON: `{"path", "sha256"}`, the path text and the hash 64
    hex digits, with `root`, a text, for a file of an input root."""
    return (
        isinstance(value, dict)
        and set(value) in _KEYS
        and isinstance(value["path"], str)
        and isinstance(value["sha256"], str)
        and _SHA256.fullmatch(value["sha256"]) is not None
        and isinstance(value.get("root", ""), str)
    )


def with_absolute_paths(params: Any, roots: Mapping[str, Path]) -> Any:
    """`params` (JSON) with each input file of an input root (`roots`, by name) as the call
    file holds it, `{"path": <absolute>, "sha256"}`; one of a root not in `roots` is left as
    it is."""
    if _is_file_json(params):
        base = roots.get(params["root"]) if "root" in params else None
        if base is None:
            return params
        return {"path": (Path(os.path.abspath(base)) / params["path"]).as_posix(), "sha256": params["sha256"]}
    if isinstance(params, dict):
        return {k: with_absolute_paths(v, roots) for k, v in params.items()}
    if isinstance(params, list):
        return [with_absolute_paths(v, roots) for v in params]
    return params


def input_files_of(params: Any, at: str = "") -> list[dict[str, str]]:
    """The input files among a task's params as JSON: each value, at any depth, that is an
    input file's JSON (`{"path", "sha256"}`, the hash 64 hex digits, with `root` for a file
    of an input root), as `{"param", "root", "path", "sha256"}` (`root` only when it has
    one), `param` the value's place in the params (`notes/0`: a list's first item under
    `notes`), in the order of the params."""
    if _is_file_json(params):
        return [{"param": at, **params}]
    if isinstance(params, dict):
        items: list[tuple[Any, Any]] = list(params.items())
    elif isinstance(params, (list, tuple)):
        items = list(enumerate(params))
    else:
        return []
    return [f for k, v in items for f in input_files_of(v, f"{at}/{k}" if at else str(k))]
