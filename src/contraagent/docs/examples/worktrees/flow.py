"""Each unit's change made in a git worktree of its own, then merged into the branch the
run's working directory has checked out.

`contraagent run` starts in the repository, with a clean working tree. `worktree` makes a
worktree for the unit, outside the run's working directory, and `implement` works in it
(`.options(cwd=)`). `land` commits the unit's work, merges the checked-out branch into it,
and moves that branch forward to it. A merge that conflicts stays in the worktree, and
`resolve` resolves it there, until `land` succeeds. The git tasks claim `git`, so one runs
at a time.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, encoding="utf-8")


def tree_of(unit: str) -> Path:
    """The unit's worktree: beside the repository, outside the run's working directory."""
    repo = Path.cwd()
    return repo.parent / f"{repo.name}.worktrees" / unit


@python_task(claims=("git",), rerun_on_resume=True)
def worktree(unit: str) -> str:
    """The unit's worktree, on branch work/<unit>; made only when it is not there."""
    tree, repo = tree_of(unit), Path.cwd()
    if not tree.is_dir():
        known = git("rev-parse", "--verify", "--quiet", f"work/{unit}", cwd=repo).returncode == 0
        args = [str(tree), f"work/{unit}"] if known else ["-b", f"work/{unit}", str(tree)]
        git("worktree", "add", *args, cwd=repo).check_returncode()
    return str(tree)


@python_task(claims=("git",), rerun_on_resume=True)
def land(unit: str) -> bool:
    """Commit the unit's work, merge the checked-out branch into it, and move that branch
    forward to it. False, with the merge left in the worktree, while files conflict."""
    tree, repo = tree_of(unit), Path.cwd()
    if git("ls-files", "-u", cwd=tree).stdout:
        return False
    git("add", "-A", cwd=tree)
    git("commit", "-m", unit, cwd=tree)  # exits 1 when there is nothing to commit
    head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    if git("merge", "--no-edit", head, cwd=tree).returncode != 0:
        return False
    git("merge", "--ff-only", f"work/{unit}", cwd=repo).check_returncode()
    return True


@python_task(claims=("git",), rerun_on_resume=True)
def remove_worktree(unit: str) -> None:
    tree, repo = tree_of(unit), Path.cwd()
    if tree.is_dir():
        git("worktree", "remove", "--force", str(tree), cwd=repo).check_returncode()
    git("branch", "-D", f"work/{unit}", cwd=repo)


class Change(BaseModel):
    goal: str = Field(description="the change to make")


implement = agent_task(
    "implement",
    params=Change,
    output=str,
    output_from="message",
    instructions="Make this change: $goal. Leave it uncommitted. Reply with one line on what you did.",
    max_turns=40,
    timeout_s=1800,
)


def resolved(path: Path, value: str, cwd: Path) -> list[str]:
    """No file of the task's working directory still conflicts or holds a conflict marker."""
    if git("ls-files", "-u", cwd=cwd).stdout:
        return ["files still conflict: resolve each one, then git add it"]
    markers = git("diff", "--check", "HEAD", cwd=cwd)
    return markers.stdout.splitlines()[-30:] if markers.returncode != 0 else []


resolve = agent_task(
    "resolve",
    output=str,
    output_from="message",
    validators=[resolved],
    instructions="A merge in this directory conflicts. Resolve each file so both sides' intent holds, "
    "git add it, and do not commit. Reply with one line per file.",
    max_turns=40,
    timeout_s=1800,
)


async def one(unit: str, change: Change) -> None:
    tree = await worktree(unit)
    await implement.options(cwd=tree)(unit, change)
    while not await land(unit):
        await resolve.options(cwd=tree)(unit)
    await remove_worktree(unit)


async def changes(goals: dict[str, str]) -> None:
    """Every unit at once; a unit that fails leaves its worktree for a person to look at,
    and the other units go on."""
    await asyncio.gather(*(one(u, Change(goal=g)) for u, g in goals.items()), return_exceptions=True)
