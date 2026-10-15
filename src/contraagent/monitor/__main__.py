"""`python -m contraagent.monitor ...` is `contraagent monitor ...`."""

import sys

from contraagent.cli import main

raise SystemExit(main(["monitor", *sys.argv[1:]]))
