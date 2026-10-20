A rewrite that puts back a file's old modification time and size is now seen as a
change: outside Windows, an output contract, a task's `changes=` and a recording run
also compare the file's status change time and inode, which a program cannot set back.
The relay compares the content of the files a contract names, so it sends a file
rewritten at the same size and modification time. The monitor shows a task as running
from its in-flight marker only while the marker's process has the start time the marker
holds, so a pid that another process now has no longer shows a finished task as
running, and a resumed run removes the markers an earlier attempt left.
