**Documentation for the coding agent that writes the pipeline.** `contraagent docs --pointer`
prints a block that tells a project's coding agent what to read first (`guide`, then
`tutorial`), how to check its work with nothing spent (`contraagent check`, a stub run, tests
on `StubAgent`), and that a run on the coding agents is for the person who asked for the
pipeline. The index that `contraagent docs` prints opens with the order in which an agent
reads the topics, and the README starts with asking a coding agent for a pipeline.
