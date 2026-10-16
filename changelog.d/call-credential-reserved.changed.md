`credential` is now a word of an agent task call, as `key`, `after` and `priority` are. A
call that passed a parameter named `credential` to a task with no params model now names
the credential the task runs as, and a params model of an agent task with a field named
`credential` is refused when the task is declared. Rename such a parameter.
