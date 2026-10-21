"""A child process in a group of its own, how to stop the whole group, and which processes
it holds (`members`: a Windows job lists them; a POSIX group keeps no list).

An agent CLI starts children of its own (hooks, a model client, a tool's server), so
stopping an agent stops its group, never its first process alone. Each OS has its own
group (`Groups`):

* POSIX (Linux, macOS): a session of its own (`start_new_session`), whose process group
  id is the child's pid; stopped by SIGTERM to the group, then SIGKILL (`PosixGroups`).
  A group outlives this interpreter when it is killed outright, so the caller runs a
  watchdog for it (`live_processes`; `dies_with_interpreter` is False).
* Windows: a process group of its own (`CREATE_NEW_PROCESS_GROUP`), so CTRL_BREAK reaches
  the child and not this interpreter, and a Job Object holding the child, which every
  process it starts joins; stopped by CTRL_BREAK to the group, then by terminating the
  job (`WindowsGroups`). The job is made with kill-on-close: when this interpreter ends,
  however it ends, the OS closes its handle and ends every process in it, so no watchdog
  is needed (`dies_with_interpreter` is True). A child that ends on its own releases the
  job (`release`), which then no longer kills what the child left running, as a POSIX
  group is not killed when its first process exits. A process the child starts in the
  moment before it joins the job (`adopt`, right after it is started) is not in it.

`groups` is this OS's. Each takes what it calls on the OS in its constructor, so each
can be tested on any OS against a fake.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from typing import Any, Protocol


class Groups(Protocol):
    """A child process in a group of its own, on one OS."""

    #: True when the OS ends a group that `adopt` took when this interpreter ends, however it ends.
    dies_with_interpreter: bool

    def popen_options(self) -> dict[str, Any]:
        """The `subprocess.Popen` keyword arguments that start a child in a group of its own."""
        ...

    def adopt(self, proc: subprocess.Popen) -> None:
        """Take a child started with `popen_options` as a group, right after it is started."""
        ...

    def release(self, proc: subprocess.Popen) -> None:
        """Forget the group of a child that has ended, or was stopped; never raises."""
        ...

    def terminate(self, proc: subprocess.Popen) -> bool:
        """Ask the child's group to stop. False when there is no group left to stop."""
        ...

    def kill(self, proc: subprocess.Popen) -> None:
        """End every process of the child's group now; never raises."""
        ...

    def members(self, proc: subprocess.Popen) -> list[int] | None:
        """The pids of the child's group as the OS lists them; None where it keeps no list
        (a POSIX group, or a child outside a job), so the child's descendants stand for it."""
        ...


class PosixGroups:
    """A session of its own (`start_new_session`); SIGTERM, then SIGKILL, to its process group.
    `killpg` is given in a test."""

    dies_with_interpreter = False

    def __init__(self, killpg=None) -> None:
        self._killpg = killpg or getattr(os, "killpg", None)

    def popen_options(self) -> dict[str, Any]:
        return {"start_new_session": True}

    def adopt(self, proc: subprocess.Popen) -> None:
        pass

    def release(self, proc: subprocess.Popen) -> None:
        pass

    def terminate(self, proc: subprocess.Popen) -> bool:
        return self._signal(proc, signal.SIGTERM)

    def kill(self, proc: subprocess.Popen) -> None:
        self._signal(proc, getattr(signal, "SIGKILL", signal.SIGTERM))

    def members(self, proc: subprocess.Popen) -> list[int] | None:
        return None

    def _signal(self, proc: subprocess.Popen, sig: int) -> bool:
        try:
            self._killpg(proc.pid, sig)  # type: ignore[misc]
            return True
        except (OSError, TypeError):
            return False


#: Windows: `CREATE_NEW_PROCESS_GROUP`, of the process creation flags.
CREATE_NEW_PROCESS_GROUP = 0x00000200
#: Windows: the job's processes end when its last handle closes.
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
#: Windows: `JobObjectExtendedLimitInformation`, of `SetInformationJobObject`'s classes.
_EXTENDED_LIMIT_INFORMATION = 9
#: Windows: `JobObjectBasicProcessIdList`, of `QueryInformationJobObject`'s classes.
_PROCESS_ID_LIST = 3
#: The most pids one query of a job reads.
_MAX_PIDS = 4096
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100


def _limit_information(flags: int):
    """A `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` whose limit flags are `flags` (a DWORD is 32
    bits, a SIZE_T and a ULONG_PTR the pointer's size: 144 bytes on 64-bit Windows)."""
    import ctypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class Io(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("Read", "Write", "Other", "ReadTransfer", "WriteTransfer", "OtherTransfer")]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", Basic),
            ("IoInfo", Io),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    info = Extended()
    info.BasicLimitInformation.LimitFlags = flags
    return info


def _pid_list(n: int):
    """A `JOBOBJECT_BASIC_PROCESS_ID_LIST` with room for `n` pids (two DWORDs, then
    ULONG_PTRs)."""
    import ctypes

    class PidList(ctypes.Structure):
        _fields_ = [
            ("NumberOfAssignedProcesses", ctypes.c_uint32),
            ("NumberOfProcessIdsInList", ctypes.c_uint32),
            ("ProcessIdList", ctypes.c_size_t * n),
        ]

    return PidList()


def _kernel32():
    import ctypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    from ctypes import wintypes

    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    k.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, wintypes.LPDWORD)
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k


class WindowsGroups:
    """A process group of its own and a kill-on-close Job Object; CTRL_BREAK to the group,
    then the job terminated. `kernel32` (its `CreateJobObjectW`, `SetInformationJobObject`,
    `OpenProcess`, `AssignProcessToJobObject`, `TerminateJobObject`,
    `QueryInformationJobObject`, `CloseHandle`) and
    `send_break` (`os.kill(pid, CTRL_BREAK_EVENT)`) are given in a test."""

    dies_with_interpreter = True

    def __init__(self, kernel32=None, send_break=None) -> None:
        self._k = kernel32
        self._send_break = send_break or _send_break
        self._jobs: dict[int, int] = {}  # pid -> job handle
        self._lock = threading.Lock()

    @property
    def _kernel(self):
        if self._k is None:
            self._k = _kernel32()
        return self._k

    def popen_options(self) -> dict[str, Any]:
        return {"creationflags": CREATE_NEW_PROCESS_GROUP}

    def adopt(self, proc: subprocess.Popen) -> None:
        k = self._kernel
        job = k.CreateJobObjectW(None, None)
        if not job:
            return  # the child still runs; it is stopped as a process group alone
        info = _limit_information(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        import ctypes

        handle = k.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, proc.pid)
        ok = bool(handle) and bool(k.SetInformationJobObject(job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)))
        ok = ok and bool(k.AssignProcessToJobObject(job, handle))
        if handle:
            k.CloseHandle(handle)
        if not ok:
            k.CloseHandle(job)
            return
        with self._lock:
            self._jobs[proc.pid] = job

    def release(self, proc: subprocess.Popen) -> None:
        with self._lock:
            job = self._jobs.pop(proc.pid, None)
        if job is None:
            return
        try:
            import ctypes

            info = _limit_information(0)  # what the child left running outlives the handle
            self._kernel.SetInformationJobObject(job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info))
            self._kernel.CloseHandle(job)
        except OSError:
            pass

    def terminate(self, proc: subprocess.Popen) -> bool:
        if proc.poll() is not None and not self._has_job(proc):
            return False
        try:
            self._send_break(proc.pid)
        except OSError:
            # No console shared with the child: it cannot be asked, only ended.
            self.kill(proc)
        return True

    def kill(self, proc: subprocess.Popen) -> None:
        with self._lock:
            job = self._jobs.get(proc.pid)
        try:
            if job is not None and self._kernel.TerminateJobObject(job, 1):
                return
            proc.kill()
        except OSError:
            pass

    def members(self, proc: subprocess.Popen) -> list[int] | None:
        with self._lock:
            job = self._jobs.get(proc.pid)
        if job is None:
            return None
        try:
            import ctypes

            info = _pid_list(_MAX_PIDS)
            if not self._kernel.QueryInformationJobObject(job, _PROCESS_ID_LIST, ctypes.byref(info), ctypes.sizeof(info), None):
                return None
            return [int(pid) for pid in info.ProcessIdList[: info.NumberOfProcessIdsInList]]
        except OSError:
            return None

    def _has_job(self, proc: subprocess.Popen) -> bool:
        with self._lock:
            return proc.pid in self._jobs


def _send_break(pid: int) -> None:
    os.kill(pid, getattr(signal, "CTRL_BREAK_EVENT", 1))


#: This OS's groups.
groups: Groups = WindowsGroups() if sys.platform == "win32" else PosixGroups()
