"""Where flow code created a task (`contraagent._internal.pipeline.origin`): the frames of flow code.
The loops around them and their passes: `test_passes.py`."""

import inspect

from contraagent._internal.pipeline import origin


def line_of(fn, text: str) -> int:
    """The line of `fn`'s source that contains `text`."""
    lines, first = inspect.getsourcelines(fn)
    return first + next(i for i, line in enumerate(lines) if text in line)


def test_the_frames_of_a_suspended_generator_and_its_yield_from_chain():
    def inner():
        yield "here"

    def outer():
        yield from inner()

    gen = outer()
    next(gen)
    frames = origin.generator_frames(gen)
    assert [f.function.rpartition(".")[2] for f in frames] == ["outer", "inner"]
    assert frames[1].line == line_of(inner, 'yield "here"')
    assert all(f.file == __file__ and f.loops == () for f in frames)


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
