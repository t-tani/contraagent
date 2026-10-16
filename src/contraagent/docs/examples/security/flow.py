"""A security review of each module, for the failover chain in `pipeline.toml`.

`audit` reads one module and writes its findings. `pipeline.toml` runs it on
Claude Code, and moves a task that a model's safeguards refuse to Codex CLI, then
to opencode.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from contraagent import agent_task


class Finding(BaseModel):
    severity: Literal["low", "medium", "high"]
    location: str = Field(description="the file and line, as path:line")
    issue: str = Field(description="what an attacker can do, in one sentence")


class Audit(BaseModel):
    findings: list[Finding]


audit = agent_task(
    "audit",
    instructions="You review one module of this repository for security issues. Do not change its code.",
    output=Audit,
)


def audit_all(modules: list[str]):
    """Audit every module at once."""
    for module in modules:
        audit(module, path=f"src/{module}")
