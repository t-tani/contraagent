"""Every text the package reads or writes is UTF-8, whatever the OS's code page.

Python's default for a text file and a child's text output is the locale's encoding:
UTF-8 on Linux and macOS, a code page on Windows (cp1252, cp932, ...). So every text
read or write in the package names its encoding, and every text write its newline (`\\n`;
Windows would write `\\r\\n`), checked here on the source. So does every script that
writes a committed file (a snapshot, a recording, the docs site's pages)."""

import ast
from pathlib import Path

import contraagent

SRC = Path(contraagent.__file__).parent
REPO = Path(__file__).resolve().parents[1]
#: The scripts that write committed files.
SCRIPTS = [REPO / "tests" / d for d in ("api", "cli", "fixtures")] + [REPO / "web" / "apps" / "docs" / "scripts"]

#: Subprocess calls whose `text=True` decodes the child's output.
_SUBPROCESS = {"run", "Popen", "check_output", "check_call"}


def _mode(call: ast.Call, position: int) -> str | None:
    """The mode a call to `open` names, None when it is not a constant."""
    for k in call.keywords:
        if k.arg == "mode":
            return k.value.value if isinstance(k.value, ast.Constant) else None
    if len(call.args) > position:
        arg = call.args[position]
        return arg.value if isinstance(arg, ast.Constant) else None
    return "r"


def _unnamed(call: ast.Call) -> str | None:
    """What a call leaves to the locale: None when it names its encoding (and newline)."""
    kws = {k.arg for k in call.keywords}
    fn = call.func
    name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
    if name == "read_text" and "encoding" not in kws:
        return "read_text without encoding"
    if name == "write_text" and not {"encoding", "newline"} <= kws:
        return "write_text without encoding and newline"
    os_open = isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "os" and fn.attr == "open"
    if name in ("open", "fdopen") and not os_open:  # os.open: a file descriptor, no text
        # open(path, mode), os.fdopen(fd, mode), Path.open(mode)
        mode = _mode(call, 0 if isinstance(fn, ast.Attribute) and fn.attr == "open" and not _is_os(fn) else 1)
        if mode is None or "b" in mode:
            return None
        if "encoding" not in kws:
            return f"open({mode!r}) without encoding"
        if set(mode) & set("wax+") and "newline" not in kws:
            return f"open({mode!r}) without newline"
    if name in _SUBPROCESS and "encoding" not in kws:
        for k in call.keywords:
            if k.arg in ("text", "universal_newlines") and not (isinstance(k.value, ast.Constant) and k.value.value is False):
                return f"{name}(text=...) without encoding"
    return None


def _is_os(fn: ast.Attribute) -> bool:
    return isinstance(fn.value, ast.Name) and fn.value.id in ("os", "io", "codecs")


def test_every_text_read_and_write_names_its_encoding():
    found = []
    for f in sorted(p for d in (SRC, *SCRIPTS) for p in d.rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and (why := _unnamed(node)):
                found.append(f"{f.relative_to(REPO if f.is_relative_to(REPO) else SRC)}:{node.lineno}: {why}")
    assert not found, "\n".join(found)
