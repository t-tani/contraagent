"""`InputFile`: a file a task is given as a param, by its path and the hash of its content.

A large input (a long text another task wrote, a data file) is not copied into the
params: the task is given an `InputFile`, which holds a path. At the task call,
contraagent takes the SHA-256 of the file's content (`bind`), and the params hold
`{"path": ..., "sha256": ...}`: the call file of an agent task, and the fingerprint,
hold the hash, so a file with other content at the same path runs the task again on a
resume. When the task is about to start, the file must still have that content
(`changed`), or the task is refused (`invalid_input`).

The path is one of the task's working directory (the `cwd` of its call options, else
`Pipeline(cwd=)`) or of the run's `out/` directory, where the tasks' output files are.
The params hold it relative to that working directory, or absolute for an output file of
a run directory outside it. A
path that leads outside both, itself or through a symbolic link, raises `ValueError`
at the task call; a relative path that climbs out with `..` raises where the
`InputFile` is made.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Sequence
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
#: The key of pydantic's validation context that holds the directory a relative path of
#: an input file's JSON is under (the working directory), for a Python task's arguments.
ROOT = "contraagent.input_root"

_SHA256 = re.compile(r"[0-9a-f]{64}")

_DESCRIPTION = (
    "A file you are given by its path, not by its content: read it with your tools. It has this content as long as the task runs."
)


class InputFile:
    """A file a task is given as a param: its path, and the SHA-256 of its content taken
    at the task call. A large input goes to a task as one (a task's output,
    `pending.input_file()` once the flow awaited it; a file on disk,
    `InputFile("in/spec.md")`) instead of being copied into its params.

    It is a field of an agent task's params model (`note: InputFile = Field(description=...)`)
    or a Python task's parameter (`def count(note: InputFile)`). The params hold
    `{"path": ..., "sha256": ...}`, the path relative to the task's working directory
    (the `cwd` of its call options, else `Pipeline(cwd=)`), and the JSON Schema of the params model tells the agent to read the
    file with its tools. The fingerprint holds the path and the hash: a file with other
    content runs the task again on a resume, and so does the same content at another path.

    The path is a file of the task's working directory, or an output file of the run (under
    its `out/`); a relative path is under that working directory. A relative path that
    climbs out with `..` raises `ValueError` here; one that leads outside both directories
    at the task call, itself or through a symbolic link, or names no file, raises
    `ValueError` at the call. When the task is about to start,
    the file must still have the content it had at the call, or the task is refused
    (`invalid_input`). A Python task is given an `InputFile` whose `path` is absolute and
    whose `sha256` is the hash taken at the call; `read_bytes` and `read_text` check the
    content against it."""

    __slots__ = ("_path", "_sha256")

    _path: Path
    _sha256: str | None

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = _checked_path(path)
        self._sha256 = None

    @classmethod
    def _recorded(cls, path: str | os.PathLike[str], sha256: str) -> InputFile:
        """An input file as a task call recorded it: its path and the hash taken then."""
        made = cls(path)
        made._sha256 = sha256
        return made

    @property
    def path(self) -> Path:
        """The path: as it was given, or, in a Python task, absolute."""
        return self._path

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
        return (self._path, self._sha256) == (other._path, other._sha256)

    def __hash__(self) -> int:
        return hash((self._path, self._sha256))

    def __repr__(self) -> str:
        hashed = f", sha256={self._sha256[:12]}..." if self._sha256 is not None else ""
        return f"InputFile({self._path.as_posix()!r}{hashed})"

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler, /) -> CoreSchema:
        """Validated from an `InputFile`, or from its JSON (`{"path", "sha256"}`); in JSON,
        that object (`bind`)."""
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

    #: The path its JSON holds: relative to the working directory, else absolute.
    shown: str
    #: The path, absolute, as given (a symbolic link in it not followed): what is hashed again when the task starts.
    path: Path
    #: The file it names, every symbolic link followed.
    real: Path
    sha256: str

    def json(self) -> dict[str, str]:
        return {"path": self.shown, "sha256": self.sha256}


def bind(file: InputFile, cwd: Path, out_dir: Path) -> Bound:
    """`file` at a task call: its path made absolute under `cwd`, checked to be a file of
    `cwd` or of `out_dir`, both as written and with every symbolic link followed, and its
    content hashed. ValueError for one outside both, or that names no file."""
    cwd = Path(os.path.abspath(cwd))
    roots = _roots(cwd, out_dir)
    given = file.path
    path = Path(os.path.normpath(given if given.is_absolute() else cwd / given))
    shown = given.as_posix()
    if not _under(path, roots + [r.resolve() for r in roots]):
        raise ValueError(f"input file {shown} is outside the working directory {cwd.as_posix()}; give a file inside it")
    try:
        real = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError(f"input file {shown} does not exist; a task is given a file that is there at its call") from None
    if not _under(real, [r.resolve() for r in roots]):
        raise ValueError(
            f"input file {shown} is a symbolic link to {real.as_posix()}, outside the working directory {cwd.as_posix()}; "
            "give a file inside it"
        )
    if not real.is_file():
        raise ValueError(f"input file {shown} is not a file")
    digest = sha256_of(real)
    if digest is None:
        raise ValueError(f"input file {shown} cannot be read")
    return Bound(shown=_shown(path, cwd), path=path, real=real, sha256=digest)


def changed(bound: Bound) -> str:
    """Why the file a task call hashed no longer has that content, as the task is about to
    start; empty when it has."""
    now = sha256_of(bound.path)
    if now is None:
        return f"input file {bound.shown} is gone; it was given to the task call with sha256 {bound.sha256[:12]}"
    if now != bound.sha256:
        return f"input file {bound.shown} changed after the task call: {_changed(bound.sha256, now)}"
    return ""


def sha256_of(path: Path) -> str | None:
    """The SHA-256 of a file's content, in hex, read in blocks; None when it cannot be read."""
    try:
        with path.open("rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except OSError:
        return None


def _changed(then: str, now: str) -> str:
    return f"sha256 {then[:12]} at the call, {now[:12]} now; the task is given the content the file had at its call"


def _checked_path(path: Any) -> Path:
    try:
        text = os.fspath(path)
    except TypeError:
        raise TypeError(f"InputFile takes a path (a str or a PathLike), not {type(path).__name__}") from None
    if not isinstance(text, str):
        raise TypeError(f"InputFile takes a path as text, not {type(text).__name__}")
    if not text:
        raise ValueError("InputFile takes a path, not an empty string")
    made = Path(text)
    if not made.is_absolute() and (os.path.normpath(text).split(os.sep)[0] == os.pardir or made.anchor):
        raise ValueError(f"input file {made.as_posix()} climbs out of the working directory with ..; give a file inside it")
    return made


def _roots(cwd: Path, out_dir: Path) -> list[Path]:
    return [cwd, Path(os.path.abspath(out_dir))]


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
    if isinstance(value, dict) and set(value) == {"path", "sha256"}:
        path, sha256 = value["path"], value["sha256"]
        if isinstance(path, str) and path and isinstance(sha256, str) and _SHA256.fullmatch(sha256):
            root = info.context.get(ROOT) if isinstance(info.context, dict) else None
            if root is not None and not Path(path).is_absolute():
                path = Path(root) / path
            return InputFile._recorded(path, sha256)
    raise ValueError('an input file is InputFile(path), or the JSON of one: {"path": "...", "sha256": "<64 hex digits>"}')


def _serialize(file: InputFile, info: core_schema.SerializationInfo) -> dict[str, str]:
    """The JSON of `file`: in a task call, as the call hashed it (`BINDINGS`); else its path
    and its hash, taken now when no task call has."""
    bindings = info.context.get(BINDINGS) if isinstance(info.context, dict) else None
    if bindings is not None:
        bound = bindings.get(file.path)
        if bound is None:
            raise ValueError(f"input file {file.path.as_posix()} was not hashed at the task call")
        return bound.json()
    digest = file.sha256 or sha256_of(file.path)
    if digest is None:
        raise ValueError(f"input file {file.path.as_posix()} cannot be read")
    return {"path": file.path.as_posix(), "sha256": digest}


def input_files_of(params: Any, at: str = "") -> list[dict[str, str]]:
    """The input files among a task's params as JSON: each value, at any depth, that is an
    input file's JSON (`{"path", "sha256"}`, the hash 64 hex digits), as `{"param", "path",
    "sha256"}`, `param` the value's place in the params (`notes/0`: a list's first item under
    `notes`), in the order of the params."""
    if isinstance(params, dict):
        if set(params) == {"path", "sha256"} and isinstance(params["path"], str) and _SHA256.fullmatch(str(params["sha256"])):
            return [{"param": at, "path": params["path"], "sha256": params["sha256"]}]
        items: list[tuple[Any, Any]] = list(params.items())
    elif isinstance(params, (list, tuple)):
        items = list(enumerate(params))
    else:
        return []
    return [f for k, v in items for f in input_files_of(v, f"{at}/{k}" if at else str(k))]
