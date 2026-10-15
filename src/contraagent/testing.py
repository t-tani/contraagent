"""A stub coding agent for tests: a `Backend` that plays scripted replies instead of an LLM.

`contraagent docs testing` shows a flow tested on it.
"""

from contraagent._internal.public import publish
from contraagent._internal.testing import (
    Reply,
    StubAgent,
    StubLaunch,
    StubTask,
    fails,
    rate_limited,
    writes,
    writes_nothing,
    writes_smallest,
)

__all__ = [
    "Reply",
    "StubAgent",
    "StubLaunch",
    "StubTask",
    "fails",
    "rate_limited",
    "writes",
    "writes_nothing",
    "writes_smallest",
]

publish(__name__, __all__)
