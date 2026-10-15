import pytest

import contraagent
from contraagent.backends import known_agents
from contraagent.routing import Route, Router, load_fallbacks


def test_create_backend():
    assert type(contraagent.create_backend("claude")).__name__ == "ClaudeBackend"
    assert known_agents() == ("claude", "omp", "omp-rpc", "opencode", "pi", "codex")
    assert type(contraagent.create_backend("opencode")).__name__ == "OpencodeBackend"
    with pytest.raises(KeyError):
        contraagent.create_backend("nope")


def test_fallbacks_from_toml(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[[defaults.fallbacks]]\nagent="omp"\nmodel="m1"\n')
    chain = load_fallbacks(f)
    assert chain == (Route("omp", "m1"),)
    router = Router(Route("claude", "opus"), chain)
    assert router.routes[1].identity == ("omp", "m1", "")


def test_unknown_agent_rejected(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[[defaults.fallbacks]]\nagent="x"\nmodel="m"\n')
    with pytest.raises(contraagent.ConfigError, match="unknown agent 'x'") as caught:
        load_fallbacks(f)
    assert isinstance(caught.value, ValueError)  # still what callers caught before


def test_every_deliberate_error_shares_one_base():
    for cls in (
        contraagent.ConfigError,
        contraagent.RoutingError,
        contraagent.CredentialError,
        contraagent.LaunchError,
        contraagent.RunLocked,
        contraagent.PluginError,
    ):
        assert issubclass(cls, contraagent.ContraagentError), cls


def test_a_table_the_config_does_not_define_is_refused_not_ignored(tmp_path):
    from contraagent import ConfigError, PipelineConfig

    f = tmp_path / "c.toml"
    f.write_text('[[default.fallbacks]]\nagent = "omp"\nmodel = "m"\n')
    with pytest.raises(ConfigError, match=r"the file has unknown keys 'default' \(did you mean defaults\?\)"):
        PipelineConfig.load(f).unknown_tables()
