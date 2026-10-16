**A coding agent's model list is read whole.** `contraagent check` and the preflight read a
coding agent's model list (`Backend.run_catalogue`) through a file, not a pipe: opencode, whose
`opencode models --verbose` is longer than a pipe holds, exits before a pipe drains when several
run at once, and the list cut short made a listed model (`opencode-go/...`) an error.
