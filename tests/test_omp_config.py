"""omp's own model chains (`OmpBackend.model_chains`): as `omp config get <key> --json` reports them."""

import json
import os

from contraagent.backends import OmpBackend
from fake_cli import write_fake_cli

#: A fake omp that answers `config get <key> --json` from SETTINGS, run in its working directory.
ANSWERS = """
import json, os, sys
settings = json.loads(os.environ["SETTINGS"])
command, key, flag = sys.argv[1:3], sys.argv[3], sys.argv[4:]
assert command == ["config", "get"] and flag == ["--json"], sys.argv
if key not in settings:
    print(f"Unknown setting: {key}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Run 'omp config list' to see available keys", file=sys.stderr)
    sys.exit(1)
open("asked-here", "a").write(key + "\\n")
print(json.dumps({"key": key, "value": settings[key], "type": "record"}, indent=2))
"""


def omp(tmp_path, settings):
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "omp", ANSWERS)
    env = {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "SETTINGS": json.dumps(settings)}
    return OmpBackend(base_env=env, trace=False)


def test_the_chains_are_what_omp_reports_in_the_launch_directory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    backend = omp(tmp_path, {"retry.modelFallback": True, "retry.fallbackChains": {"p/*": ["q/*"], "p/m": ["p/n"]}})
    chains = backend.model_chains(project)
    assert chains.describe("p/m") == "omp's config -> p/n"
    assert chains.describe("p/x") == "omp's config -> q/*"
    assert (project / "asked-here").read_text().split() == ["retry.modelFallback", "retry.fallbackChains"]


def test_no_chain_and_model_fallback_off_are_said_apart(tmp_path):
    assert (
        omp(tmp_path, {"retry.modelFallback": True, "retry.fallbackChains": {}})
        .model_chains(tmp_path)
        .describe("p/m")
        .startswith("none configured in omp's config")
    )
    off = omp(tmp_path, {"retry.modelFallback": False, "retry.fallbackChains": {"p/m": ["p/n"]}})
    assert off.model_chains(tmp_path).describe("p/m") == "off: retry.modelFallback is false in omp's config"


def test_a_setting_omp_does_not_report_is_not_known_rather_than_missing(tmp_path):
    backend = omp(tmp_path, {"retry.modelFallback": True})
    said = backend.model_chains(tmp_path).describe("p/m")
    assert said == "not known: omp config get retry.fallbackChains failed: Unknown setting: retry.fallbackChains"
