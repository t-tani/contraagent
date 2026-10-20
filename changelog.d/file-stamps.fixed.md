A rewrite that puts back a file's old modification time and size is now seen as a
change: outside Windows, the stamp an output contract, a task's `changes=` and a
recording run compare also holds the file's status change time and inode, which a
program cannot set back. `Before.stamp` is typed `tuple[int, ...] | None` for this
(it was `tuple[int, int] | None`); on Windows it still holds the two numbers. The relay
compares the content of the files a contract names, so it sends a file rewritten at the
same size and modification time. The monitor shows a task as running from its in-flight
marker only while the marker's process has the start time the marker holds, so a pid
that another process now has no longer shows a finished task as running, and a resumed
run removes the markers an earlier attempt left.
