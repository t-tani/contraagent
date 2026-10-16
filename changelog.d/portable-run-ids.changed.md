A run id is a file name on every operating system: one with `<>:"|?*`, a trailing
`.` or space, or a Windows device name such as `CON` is refused with ValueError on
every system, so a pipeline written on Linux also runs on Windows. The default run
id, the flow's name, has each such character turned into `_` (a lambda runs as
`_lambda_`).
