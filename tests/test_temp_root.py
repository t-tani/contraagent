"""`temp_root`: one owner-only directory per user, `<temp dir>/contraagent-<uid>`."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from contraagent._internal.backends import base
from contraagent._internal.backends.base import temp_dir, temp_root

pytestmark = pytest.mark.skipif(not hasattr(os, "getuid"), reason="users are kept apart only where there are uids")


@pytest.fixture
def systmp(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def own(systmp: Path) -> Path:
    return systmp / f"contraagent-{os.getuid()}"


def mode(p: Path) -> int:
    return stat.S_IMODE(os.lstat(p).st_mode)


def test_each_user_has_an_owner_only_directory_and_nothing_else_is_made(systmp):
    root = temp_root()
    assert root == own(systmp) and mode(root) == 0o700
    made = temp_dir("x-")
    assert made.parent == root and mode(made) == 0o700
    assert temp_root() == root  # a second call takes it as it is
    # Only our one directory: the temp dir is the whole process's, and a thread of another test may add files there.
    assert [n for n in os.listdir(systmp) if n.startswith("contraagent-")] == [root.name]


def test_our_directory_others_can_reach_is_made_owner_only(systmp):
    own(systmp).mkdir(mode=0o755)
    os.chmod(own(systmp), 0o777)
    assert mode(temp_root()) == 0o700


def test_a_symlink_is_refused(systmp):
    (systmp / "elsewhere").mkdir()
    own(systmp).symlink_to(systmp / "elsewhere")
    with pytest.raises(PermissionError, match="symlink"):
        temp_root()
    assert os.listdir(systmp / "elsewhere") == []


def test_a_file_is_refused(systmp):
    own(systmp).write_text("")
    with pytest.raises(PermissionError, match="not a directory"):
        temp_root()


def test_another_users_directory_is_refused_and_left_as_it_is(systmp, monkeypatch):
    own(systmp).mkdir(mode=0o777)
    real_fstat = os.fstat

    def fstat(fd):
        values = list(real_fstat(fd))
        values[stat.ST_UID] = os.getuid() + 1
        return os.stat_result(values)

    monkeypatch.setattr(base.os, "fstat", fstat)
    monkeypatch.setattr(base.os, "fchmod", lambda *a: pytest.fail("changed the mode of another user's directory"))
    with pytest.raises(PermissionError, match="owned by uid"):
        temp_root()


def test_a_directory_removed_at_exit_is_owner_only_and_removed_with_its_contents(systmp, monkeypatch):
    monkeypatch.setattr(base, "_exit_dirs", [])  # the directories other tests of this process made stay
    made = base.exit_dir("mcp-")
    (made / "index.mcp.json").write_text("{}")
    assert made.parent == temp_root() and mode(made) == 0o700
    base.remove_exit_dirs()
    assert not made.exists()
    base.remove_exit_dirs()  # nothing left to remove
