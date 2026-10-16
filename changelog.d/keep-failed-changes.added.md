`keep_failed_changes` (`agent_task(keep_failed_changes=True)`, or
`keep_failed_changes = true` in `[tasks.<kind>]`) leaves the files a failed attempt
created under its `changes` patterns in place instead of removing them, so the next
attempt starts from them. The journal row lists them as `changes.kept`, and the monitor
shows them as kept. A kind that keeps them needs `changes` patterns, and
`contraagent check` reports a task table that sets it for a kind without any.
