An agent task's output may be rows: `agent_task(output=Rows[Finding])` declares a JSON
Lines file whose every line is one `Finding`, checked line by line, each error naming its
line. The agent adds each row as soon as it has it; the flow, the validators and the
tasks it is passed to get a `Rows`, a list of the models. The call file says
`output.format: "jsonl"`, a stub run's example is one row, a Python task may return
`Rows` too, and the monitor shows the file's rows and the row model's fields
(`ContractSpec.format`).
