contraagent runs on macOS and Windows as well as Linux; "Operating systems" in the guide (`contraagent docs guide`) lists what differs. psutil is a new dependency: it reads the host's processes and free memory on every OS. Every text contraagent reads or writes is UTF-8 with LF line ends, whatever the OS's code page. On Windows:
- an agent session runs in a Job Object, which the OS ends with the pipeline's process however it ends;
- a coding agent installed by npm (`claude.cmd`) is started as the program its batch file runs, so a prompt reaches it unchanged;
- a plugin's hook scripts run under the bash of Git for Windows (`CONTRAAGENT_BASH`, `CLAUDE_CODE_GIT_BASH_PATH`), never the WSL `bash.exe` of `System32`;
- a prompt goes over stdin past 16,000 characters (`STDIN_THRESHOLD`).
