"""Where flow code created a task (`contraagent._internal.pipeline.origin`): the frames of flow code.
The loops around them and their passes: `test_passes.py`."""

import inspect

from contraagent._internal.pipeline import origin


def line_of(fn, text: str) -> int:
    """The line of `fn`'s source that contains `text`."""
    lines, first = inspect.getsourcelines(fn)
    return first + next(i for i, line in enumerate(lines) if text in line)


def test_the_frames_of_a_suspended_coroutine_and_its_await_chain():
    class Wait:
        def __await__(self):
            yield "here"

    async def inner():
        await Wait()

    async def outer():
        await inner()

    coro = outer()
    coro.send(None)
    frames = origin.suspended_frames(coro)
    assert [f.function.rpartition(".")[2] for f in frames] == ["outer", "inner", "__await__"]
    assert frames[1].line == line_of(inner, "await Wait()")
    assert all(f.file == __file__ and f.loops == () for f in frames)
    coro.close()


def test_frames_here_keeps_flow_code_and_skips_comprehensions():
    import sys

    def helper():
        return origin.frames_here(sys._getframe())

    def caller():
        return [helper() for _ in range(1)][0]

    frames = caller()
    names = [f.function.rpartition(".")[2] for f in frames]
    assert names[-3:] == ["test_frames_here_keeps_flow_code_and_skips_comprehensions", "caller", "helper"]
    assert "<listcomp>" not in names
