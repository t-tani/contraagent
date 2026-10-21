"""omp's own model chains (`OmpBackend.model_chains`): read from the directory `omp config path` reports."""

import os

from contraagent.backends import OmpBackend
from fake_cli import write_fake_cli


def omp(tmp_path, body):
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "omp", body)
    return OmpBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"}, trace=False)


def test_the_global_config_is_the_one_in_the_directory_omp_reports(tmp_path):
    agent_dir = tmp_path / "profile"
    backend = omp(tmp_path, f"print({str(agent_dir)!r})")
    said = backend.model_chains(tmp_path).describe("p/m")
    assert said.startswith(f"none configured in {agent_dir / 'config.yml'} ")


def test_a_failed_config_path_is_reported_and_no_directory_is_guessed(tmp_path):
    fails = "import sys\nprint('loading profile', file=sys.stderr)\nprint('no such profile: work', file=sys.stderr)\nsys.exit(1)"
    backend = omp(tmp_path, fails)
    said = backend.model_chains(tmp_path).describe("p/m")
    assert said == "not known: omp config path failed: no such profile: work"
