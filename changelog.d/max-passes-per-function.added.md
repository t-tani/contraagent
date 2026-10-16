`@max_passes(n)` bounds each `while` loop of one generator function of flow code at `n`
passes, in every call of it, in place of the run's `max_passes`. `TooManyPasses` names
the function whose bound a loop passed. The decorator on a function that is not a
generator function, or that has no `while` loop, raises `TypeError`.
