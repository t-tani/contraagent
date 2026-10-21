"""The platform layer (`_internal/platform`): each OS's implementation behind its interface.

The implementation of the OS the tests run on is tested against the OS itself; the others
against a fake of the calls they make, so a Linux run still tests the Windows code."""

import ctypes
import errno
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import psutil
import pytest

from contraagent._internal.platform import groups as groups_mod
from contraagent._internal.platform import processes
from contraagent._internal.platform.commands import CommandError, PosixCommands, WindowsCommands
from contraagent._internal.platform.groups import (
    CREATE_NEW_PROCESS_GROUP,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    PosixGroups,
    WindowsGroups,
)
from contraagent._internal.platform.links import PosixLinks, WindowsLinks
from contraagent._internal.platform.locks import PosixLocks, WindowsLocks

posix = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups and flock")
linux = pytest.mark.skipif(sys.platform != "linux", reason="/proc")


def _sleeper(**kw) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **kw)


# --- processes ----------------------------------------------------------------------------


def test_this_process_is_itself_and_not_another_start():
    me = os.getpid()
    ticks = processes.start_ticks(me)
    assert ticks is not None
    assert processes.identity_ok(me, ticks)
    assert not processes.identity_ok(me, ticks + 1)  # a recycled pid: a later start
    assert not processes.identity_ok(me, None)  # no start recorded: not trusted
    assert not processes.identity_ok(None, ticks)


@pytest.mark.parametrize("starts", [processes.PsutilStarts(), pytest.param(processes.LinuxStarts(), marks=linux)])
def test_each_way_of_reading_a_start_is_stable_and_ends_with_the_process(starts):
    proc = _sleeper()
    try:
        first = starts(proc.pid)
        assert first is not None and first == starts(proc.pid)
        assert processes.identity_ok(proc.pid, first, starts=starts)
    finally:
        proc.kill()
        proc.wait()
    deadline = time.monotonic() + 5
    while processes.identity_ok(proc.pid, first, starts=starts) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not processes.identity_ok(proc.pid, first, starts=starts), _seen(proc.pid, first, starts)


def _seen(pid: int, first: int, starts) -> str:
    """What psutil reports of `pid`, for a failure's message."""
    try:
        p = psutil.Process(pid)
        return f"pid {pid}: {p.name()} {p.status()}, start {starts(pid)} (recorded {first}), alive {processes.alive(pid)}"
    except psutil.Error as e:
        return f"pid {pid}: {type(e).__name__}"


def test_linux_starts_read_field_22_after_the_command_name(tmp_path):
    (tmp_path / "7").mkdir()
    fields = ["S"] + [str(i) for i in range(1, 19)] + ["123456"] + ["0"] * 10
    (tmp_path / "7" / "stat").write_text("7 (a) b (c)) " + " ".join(fields))
    assert processes.LinuxStarts(str(tmp_path))(7) == 123456
    assert processes.LinuxStarts(str(tmp_path))(8) is None


@posix
def test_a_zombie_is_not_alive():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 10
    while processes.alive(proc.pid) and time.monotonic() < deadline:
        time.sleep(0.05)  # exited, not yet collected: a zombie
    assert not processes.alive(proc.pid)
    proc.wait()


def test_the_scan_and_environment_of_a_child():
    proc = _sleeper(env={**os.environ, "CONTRAAGENT_TASK": "k", "OTHER": "x"})
    try:
        deadline = time.monotonic() + 10
        while proc.pid not in processes.scan() and time.monotonic() < deadline:
            time.sleep(0.05)
        seen = processes.scan()[proc.pid]
        assert seen.ppid == os.getpid() and "time.sleep(60)" in seen.cmd
        assert abs(seen.started - time.time()) < 60
        if sys.platform != "darwin":  # macOS shows another process's environment to no one
            assert processes.environ(proc.pid, "CONTRAAGENT_") == {"CONTRAAGENT_TASK": "k"}
    finally:
        proc.kill()
        proc.wait()
    assert processes.environ(proc.pid) == {}


class _Process:
    """A process as `processes.scan` reads it, whose read gives `info` or raises `error`."""

    def __init__(self, pid, info=None, error=None):
        self.pid, self.info, self.error = pid, info, error

    def as_dict(self, attrs):
        if self.error is not None:
            raise self.error
        return {a: self.info.get(a) for a in attrs}


def test_the_scan_leaves_out_a_process_that_could_not_be_read():
    info = {"ppid": 1, "cmdline": ["agent", "-p"], "create_time": 5.0, "status": psutil.STATUS_RUNNING}
    ended = SystemError("<built-in function proc_cmdline> returned a result with an exception set")
    seen = processes.scan(
        [
            _Process(10, info),
            _Process(11, error=ended),  # psutil 7.2.2 on macOS, a process ending while read
            _Process(12, error=psutil.NoSuchProcess(12)),
            _Process(13, {**info, "status": psutil.STATUS_ZOMBIE}),
        ]
    )
    assert seen == {10: processes.Proc(10, 1, "agent -p", 5.0)}


# --- groups: POSIX, against the OS -------------------------------------------------------

_TREE = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(child.pid, flush=True)
time.sleep(60)
"""


@posix
@pytest.mark.parametrize("how", ["terminate", "kill"])
def test_a_posix_group_stops_with_its_children(how):
    g = PosixGroups()
    with subprocess.Popen([sys.executable, "-c", _TREE], stdout=subprocess.PIPE, text=True, **g.popen_options()) as proc:
        g.adopt(proc)
        assert proc.stdout is not None
        child = int(proc.stdout.readline())
        if how == "terminate":
            assert g.terminate(proc)
        else:
            g.kill(proc)
        # The child holds the write end of the parent's stdout and never closes it, so the
        # end of that stdout means both have ended: the exit of a process closes its files.
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            state = _state(child)
            g.kill(proc)
            pytest.fail(state)
        g.release(proc)
    assert out == ""


def _state(pid: int) -> str:
    """What psutil reports of `pid`, for a failure's message."""
    try:
        p = psutil.Process(pid)
        return f"pid {pid}: {p.status()}, parent {p.ppid()}, group {os.getpgid(pid)}"
    except (psutil.Error, OSError) as e:
        return f"pid {pid}: {type(e).__name__}"


@posix
def test_a_posix_group_that_has_ended_is_not_signalled():
    g = PosixGroups()
    with _sleeper(**g.popen_options()) as proc:
        proc.kill()
    # Its only process has been reaped (`Popen.__exit__` waits): no group is left.
    assert not g.terminate(proc)


@posix
def test_posix_groups_send_the_signals_to_the_group():
    sent = []
    g = PosixGroups(killpg=lambda pgid, sig: sent.append((pgid, sig)))
    proc = SimpleNamespace(pid=42)
    assert g.popen_options() == {"start_new_session": True} and not g.dies_with_interpreter
    assert g.terminate(proc)  # type: ignore[arg-type]
    g.kill(proc)  # type: ignore[arg-type]
    assert [p for p, _ in sent] == [42, 42] and sent[0][1] != sent[1][1]


# --- groups: Windows, against a fake kernel32 ---------------------------------------------


class Kernel32:
    """The kernel32 calls `WindowsGroups` makes, recorded."""

    def __init__(self, *, assign=True) -> None:
        self.calls: list[tuple] = []
        self.assign = assign
        self.flags: dict[int, int] = {}

    def CreateJobObjectW(self, attributes, name):
        self.calls.append(("create",))
        return 100

    def SetInformationJobObject(self, job, cls, info, size):
        self.flags[job] = info._obj.BasicLimitInformation.LimitFlags  # info: byref(the structure)
        self.calls.append(("set", job, cls, size))
        return 1

    def OpenProcess(self, access, inherit, pid):
        self.calls.append(("open", pid))
        return 200

    def AssignProcessToJobObject(self, job, handle):
        self.calls.append(("assign", job, handle))
        return 1 if self.assign else 0

    def TerminateJobObject(self, job, code):
        self.calls.append(("terminate", job))
        return 1

    def QueryInformationJobObject(self, job, cls, info, size, returned):
        self.calls.append(("query", job, cls))
        listed = info._obj  # info: byref(the structure)
        for i, pid in enumerate((7, 8)):
            listed.ProcessIdList[i] = pid
        listed.NumberOfAssignedProcesses = listed.NumberOfProcessIdsInList = 2
        return 1

    def CloseHandle(self, handle):
        self.calls.append(("close", handle))
        return 1


class Proc:
    def __init__(self, pid=7) -> None:
        self.pid, self.killed, self.code = pid, False, None

    def poll(self):
        return self.code

    def kill(self):
        self.killed = True


def test_the_job_information_has_the_windows_layout():
    info = groups_mod._limit_information(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
    assert ctypes.sizeof(info) == (144 if ctypes.sizeof(ctypes.c_void_p) == 8 else 112)
    assert info.BasicLimitInformation.LimitFlags == 0x2000


def test_a_windows_child_joins_a_job_that_ends_with_this_interpreter():
    k = Kernel32()
    g = WindowsGroups(kernel32=k, send_break=lambda pid: None)
    assert g.popen_options() == {"creationflags": CREATE_NEW_PROCESS_GROUP} and g.dies_with_interpreter
    proc = Proc()
    g.adopt(proc)  # type: ignore[arg-type]
    assert ("assign", 100, 200) in k.calls and ("close", 200) in k.calls  # the process handle is not kept
    assert k.flags[100] == JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    g.kill(proc)  # type: ignore[arg-type]
    assert ("terminate", 100) in k.calls and not proc.killed
    proc.code = 0
    g.release(proc)  # type: ignore[arg-type]
    assert k.flags[100] == 0 and k.calls[-1] == ("close", 100)  # what it left running is not killed
    assert not g.terminate(proc)  # type: ignore[arg-type]


def test_a_windows_group_is_asked_with_ctrl_break_then_its_job_is_ended():
    k, breaks = Kernel32(), []
    g = WindowsGroups(kernel32=k, send_break=breaks.append)
    proc = Proc()
    g.adopt(proc)  # type: ignore[arg-type]
    assert g.terminate(proc)  # type: ignore[arg-type]
    assert breaks == [7] and ("terminate", 100) not in k.calls

    def no_console(pid):
        raise OSError("no console")

    g = WindowsGroups(kernel32=k, send_break=no_console)
    g.adopt(proc)  # type: ignore[arg-type]
    assert g.terminate(proc)  # type: ignore[arg-type]
    assert ("terminate", 100) in k.calls  # it cannot be asked: it is ended


def test_a_windows_job_lists_the_processes_of_its_group():
    k = Kernel32()
    g = WindowsGroups(kernel32=k, send_break=lambda pid: None)
    proc = Proc()
    assert g.members(proc) is None  # type: ignore[arg-type]  # no job yet
    g.adopt(proc)  # type: ignore[arg-type]
    assert g.members(proc) == [7, 8]  # type: ignore[arg-type]
    assert ("query", 100, 3) in k.calls
    assert PosixGroups().members(proc) is None  # type: ignore[arg-type]  # a POSIX group keeps no list


def test_a_windows_child_outside_a_job_is_killed_alone():
    k = Kernel32(assign=False)  # already in a job that does not nest
    g = WindowsGroups(kernel32=k, send_break=lambda pid: None)
    proc = Proc()
    g.adopt(proc)  # type: ignore[arg-type]
    assert ("close", 100) in k.calls  # the job is not kept
    g.kill(proc)  # type: ignore[arg-type]
    assert proc.killed and ("terminate", 100) not in k.calls


# --- locks ---------------------------------------------------------------------------------


@posix
def test_a_posix_lock_is_held_by_one_open_file(tmp_path):
    locks, path = PosixLocks(), tmp_path / "x.lock"
    a, b = os.open(path, os.O_CREAT | os.O_RDWR), os.open(path, os.O_RDWR)
    try:
        assert locks.try_lock(a)
        assert not locks.try_lock(b)
        held = subprocess.run(
            [sys.executable, "-c", f"import fcntl, os; fcntl.flock(os.open({str(path)!r}, os.O_RDWR), fcntl.LOCK_EX | fcntl.LOCK_NB)"],
            capture_output=True,
        )
        assert held.returncode != 0  # another process is refused it too
        got = threading.Event()
        waiter = threading.Thread(target=lambda: (locks.lock(b), got.set()))
        waiter.start()
        assert not got.wait(0.2)
        locks.unlock(a)
        assert got.wait(5)
        waiter.join()
    finally:
        os.close(a)
        os.close(b)


class Fcntl:
    """`flock` that fails as a file system without locks does (`ENOLCK`), or as a held lock does."""

    LOCK_EX, LOCK_NB, LOCK_UN = 2, 4, 8

    def __init__(self, errno_: int) -> None:
        self.errno = errno_

    def flock(self, fd: int, op: int) -> None:
        raise OSError(self.errno, os.strerror(self.errno))


def test_only_a_lock_held_elsewhere_reads_as_held():
    assert not PosixLocks(Fcntl(errno.EWOULDBLOCK)).try_lock(0)
    with pytest.raises(OSError) as raised:
        PosixLocks(Fcntl(errno.ENOLCK)).try_lock(0)
    assert raised.value.errno == errno.ENOLCK


class Msvcrt:
    """`msvcrt.locking` over a shared table of locked (file, offset) regions."""

    LK_UNLCK, LK_NBLCK = 0, 2

    def __init__(self) -> None:
        self.held: dict[tuple[int, int], int] = {}

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        st, pos = os.fstat(fd), os.lseek(fd, 0, os.SEEK_CUR)
        key = (st.st_ino, pos)
        if mode == self.LK_UNLCK:
            if self.held.get(key) != fd:
                raise OSError("not locked")
            del self.held[key]
        elif key in self.held:
            raise OSError("locked")
        else:
            self.held[key] = fd


def test_a_windows_lock_is_on_the_first_byte_whatever_the_position(tmp_path):
    m = Msvcrt()
    locks, path = WindowsLocks(m, poll_s=0.01), tmp_path / "x.lock"
    a, b = os.open(path, os.O_CREAT | os.O_RDWR), os.open(path, os.O_RDWR)
    try:
        os.write(b, b"some text")  # b's position is past the first byte
        assert locks.try_lock(a)
        assert not locks.try_lock(b)
        got = threading.Event()
        waiter = threading.Thread(target=lambda: (locks.lock(b), got.set()))
        waiter.start()
        assert not got.wait(0.1)
        locks.unlock(a)
        assert got.wait(5)
        waiter.join()
        assert list(m.held.values()) == [b]
    finally:
        os.close(a)
        os.close(b)


# --- what the monitor reads of a process ---------------------------------------------------


def test_a_launch_whose_environment_is_not_readable_is_known_by_its_telemetry_line():
    from contraagent._internal.platform import envvars, telemetry
    from contraagent._internal.runs.procs import _env_of_telemetry

    cmd = f"claude -p {telemetry.line('r1', 'review', '', 'review', None)}"
    assert _env_of_telemetry(cmd) == {envvars.RUN: "r1", envvars.KIND: "review", envvars.UNIT: "", envvars.TASK: "review"}
    assert _env_of_telemetry("claude -p") == {}


# --- commands -------------------------------------------------------------------------------

#: What npm's cmd-shim writes for a package's bin, as `claude.cmd`.
_NPM_SHIM = r"""@ECHO off
GOTO start
:find_dp0
SET dp0=%~dp0
EXIT /b
:start
SETLOCAL
CALL :find_dp0

IF EXIST "%dp0%\node.exe" (
  SET "_prog=%dp0%\node.exe"
) ELSE (
  SET "_prog=node"
  SET PATHEXT=%PATHEXT:;.JS;=;%
)

endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\node_modules\@anthropic-ai\claude-code\cli.js" %*
"""


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_a_posix_command_line_starts_as_it_is():
    assert PosixCommands().resolve(["claude", "-p", "50% & more"]) == ["claude", "-p", "50% & more"]


def test_a_windows_program_is_looked_up_on_the_given_path(tmp_path):
    asked = []
    found = {"claude": str(tmp_path / "claude.exe")}

    def which(name, path):
        asked.append(path)
        return found.get(name)

    assert WindowsCommands(which).resolve(["claude", "-p", "x"], "C:\\bin") == [found["claude"], "-p", "x"]
    assert asked == ["C:\\bin"]
    assert WindowsCommands(which).resolve(["missing", "-p"]) == ["missing", "-p"]  # the OS reports it


def test_an_npm_batch_file_runs_its_script_with_node(tmp_path):
    _write(tmp_path / "claude.cmd", _NPM_SHIM)
    found = {"claude": str(tmp_path / "claude.cmd"), "node": "C:\\node\\node.exe"}
    commands = WindowsCommands(lambda name, path: found.get(name))
    argv = commands.resolve(["claude", "-p", "50% & more"])
    assert argv[0] == "C:\\node\\node.exe" and argv[2:] == ["-p", "50% & more"]
    assert argv[1].endswith("cli.js") and argv[1].startswith(str(tmp_path))
    (tmp_path / "node.exe").write_bytes(b"")  # npm's own node beside it comes first
    assert commands.resolve(["claude"])[0] == str(tmp_path / "node.exe")


def test_an_npm_batch_file_of_a_program_runs_the_program(tmp_path):
    _write(tmp_path / "codex.cmd", '@"%~dp0\\node_modules\\@openai\\codex\\bin\\codex.exe" %*\n')
    argv = WindowsCommands(lambda name, path: str(tmp_path / "codex.cmd")).resolve(["codex", "exec"])
    assert argv[0].endswith("codex.exe") and argv[1:] == ["exec"]


def test_a_batch_file_that_is_not_npms_is_refused(tmp_path):
    _write(tmp_path / "tool.bat", "@echo %*\n")
    with pytest.raises(CommandError, match="batch file"):
        WindowsCommands(lambda name, path: str(tmp_path / "tool.bat")).resolve(["tool", "x"])
    _write(tmp_path / "js.cmd", '@"%~dp0\\x.js" %*\n')
    with pytest.raises(CommandError, match="node is not on PATH"):
        WindowsCommands(lambda name, path: str(tmp_path / "js.cmd") if name == "js" else None).resolve(["js"])


def test_a_hook_runs_under_the_bash_on_path_on_posix():
    assert PosixCommands().bash({}) == "bash"


def test_a_windows_hook_runs_under_the_bash_of_git_for_windows_never_wsl(tmp_path):
    wsl = "C:\\Windows\\System32\\bash.exe"
    assert WindowsCommands(lambda name, path: wsl).bash({}) is None
    assert WindowsCommands(lambda name, path: wsl).bash({"CLAUDE_CODE_GIT_BASH_PATH": "D:\\git\\bash.exe"}) == "D:\\git\\bash.exe"
    assert WindowsCommands(lambda name, path: None).bash({"CONTRAAGENT_BASH": "E:\\b", "CLAUDE_CODE_GIT_BASH_PATH": "D:"}) == "E:\\b"
    assert WindowsCommands(lambda name, path: "C:\\Git\\usr\\bin\\bash.exe").bash({}) == "C:\\Git\\usr\\bin\\bash.exe"
    installed = tmp_path / "Git" / "bin" / "bash.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"")
    assert WindowsCommands(lambda name, path: wsl).bash({"ProgramFiles": str(tmp_path)}) == str(installed)


# --- links ----------------------------------------------------------------------------------


@posix
def test_a_posix_link_is_a_symbolic_link(tmp_path):
    (tmp_path / "dir").mkdir()
    (tmp_path / "file").write_text("x", encoding="utf-8", newline="\n")
    for name in ("dir", "file"):
        PosixLinks().link(tmp_path / name, tmp_path / f"{name}-link")
        assert os.readlink(tmp_path / f"{name}-link") == str(tmp_path / name)


def test_a_windows_link_is_a_symbolic_link_where_the_user_may_make_one(tmp_path):
    (tmp_path / "dir").mkdir()
    (tmp_path / "file").write_text("x", encoding="utf-8", newline="\n")
    made = []

    def refused(*a, **kw):
        raise OSError("A required privilege is not held by the client")

    def record(how):
        return lambda source, link, **kw: made.append((how, source, link))

    allowed = WindowsLinks(symlink=record("symlink"))
    allowed.link(tmp_path / "dir", tmp_path / "a")
    assert made[-1][0] == "symlink"
    plain = WindowsLinks(symlink=refused, junction=record("junction"), hardlink=record("hardlink"))
    plain.link(tmp_path / "dir", tmp_path / "b")
    plain.link(tmp_path / "file", tmp_path / "c")
    assert [m[0] for m in made[-2:]] == ["junction", "hardlink"]
    other_volume = WindowsLinks(symlink=refused, hardlink=refused, copy=record("copy"))
    other_volume.link(tmp_path / "file", tmp_path / "d")
    assert made[-1] == ("copy", str(tmp_path / "file"), str(tmp_path / "d"))
