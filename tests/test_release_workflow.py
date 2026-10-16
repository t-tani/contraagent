"""The release workflow hands npm paths it reads as files."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"


def test_npm_publish_is_given_a_path_npm_reads_as_a_file():
    # npm reads `dir/name.tgz` as a GitHub repository `owner/repo`; `./dir/name.tgz` is a file.
    targets = re.findall(r'^\s+npm publish "([^"]+)"', WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE)
    assert targets, "the workflow runs no npm publish"
    assert len(targets) == 2 and all(t.startswith("./") for t in targets), targets
