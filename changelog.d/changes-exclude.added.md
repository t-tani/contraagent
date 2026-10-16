A `changes=` pattern that starts with `!` leaves out what it matches, and everything
under a directory it matches: `["**", "!.git/**"]` covers every file of the working
directory but the version control directory, and the scan does not enter a directory
left out. A list of `!` patterns alone covers nothing and is refused where the task is
declared.
