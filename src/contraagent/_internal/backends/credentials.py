"""Credentials: which identity, and so which contract, a coding agent's API calls are billed to.

A credential is *what* a launch authenticates as, independent of the coding
agent: a subscription login, an API key of a ZDR organization, a Bedrock role.
Each `Backend` decides *how* (if at all) it can use one: which environment
variables or flags select it, and whether it can guarantee that nothing else
it would load by default (a stored login, a key left in the environment) is
used instead (`Backend.bind_credential`).

    [credentials.personal]
    type = "subscription"

    [credentials.zdr]
    type = "api_key"
    provider = "anthropic"
    key = "env:ZDR_ANTHROPIC_API_KEY"     # or "file:/run/secrets/zdr-key"
    traits = ["zdr"]

`traits` are free-form labels a task's requirements are matched against
(`agent_task(..., requires=["zdr"])`): which task may use which credential is
decided by the routing plan, not here. `max_five_hour_pct` and `max_seven_day_pct`
are the account's quota caps (`routing.quota`).

Secrets are never stored: a credential names where the value comes from
(`env:NAME`, `file:/path`), and the value is read in the launching process.
A secret that does not resolve fails the launch; it never falls back.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, TypeAdapter, WithJsonSchema

from contraagent._internal.errors import ContraagentError


class CredentialError(ContraagentError):
    """A credential that cannot be used: unknown, unsupported by an agent, or a secret that does not resolve."""


# --- secrets ----------------------------------------------------------------


@dataclass(frozen=True)
class Secret:
    """Where a secret's value comes from: `env:NAME` or `file:/path`. Never the value itself."""

    source: str

    def __post_init__(self) -> None:
        kind, _, ref = self.source.partition(":")
        if kind not in ("env", "file") or not ref:
            raise ValueError(f"secret {self.source!r}: write env:NAME or file:/path")

    def resolve(self, env: dict[str, str]) -> str:
        kind, _, ref = self.source.partition(":")
        if kind == "env":
            if not env.get(ref):
                raise CredentialError(f"secret env:{ref} is not set")
            return env[ref]
        try:
            value = Path(os.path.expanduser(ref)).read_text().strip()
        except OSError as exc:
            raise CredentialError(f"secret file:{ref}: {exc}") from exc
        if not value:
            raise CredentialError(f"secret file:{ref} is empty")
        return value

    def __str__(self) -> str:
        return self.source


def _secret(v):
    return v if isinstance(v, Secret) else Secret(str(v))


def _secret_text(v: Secret) -> str:
    """Serialize a secret as its source text. A plain function rather than
    the `str` builtin: pydantic < 2.8 inspects the serializer's signature,
    and builtins have none."""
    return str(v)


#: A secret in a credential: written `env:NAME` / `file:/path`, recorded as that text, never resolved here.
SecretField = Annotated[
    Secret,
    BeforeValidator(_secret),
    PlainSerializer(_secret_text, return_type=str),
    WithJsonSchema({"type": "string", "pattern": "^(env|file):.+", "description": "env:NAME or file:/path"}),
]


# --- credential types -------------------------------------------------------


# `frozen` is a class keyword, repeated on every subclass, rather than a `model_config`
# entry: type checkers read only the keyword, and only a frozen field may be narrowed
# by a subclass, which is what pins `type` to each subclass's own literal.
class CredentialBase(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    #: The name the config gives it; what journals and the monitor show.
    name: str = ""
    #: Labels a task's `requires` is matched against ("zdr", "company-billing", ...).
    traits: frozenset[str] = frozenset()
    #: Keep the coding agent from using anything it would load by default
    #: (stored logins, keys in its own config) instead of this credential.
    isolate: bool = True
    #: Quota caps: past this 5-hour / weekly usage (%), as the coding agent last reported it
    #: for this account, the credential rests until that window resets (`routing.quota`).
    #: On a pool, the cap of each member that sets none.
    max_five_hour_pct: float | None = Field(default=None, gt=0, le=100)
    max_seven_day_pct: float | None = Field(default=None, gt=0, le=100)
    #: The `type = "..."` the config names it by; each subclass pins it to its own literal.
    type: str

    @property
    def label(self) -> str:
        return self.name or self.type

    def describe(self) -> dict:
        """What may be recorded: never a secret, only where it comes from."""
        return self.model_dump(mode="json")

    def secret_sources(self) -> tuple[str, ...]:
        """The parent variables this credential's secrets are read from. The child gets
        the value under the name its agent reads, never the source variable itself."""
        return tuple(v.source.partition(":")[2] for v in self.__dict__.values() if isinstance(v, Secret) and v.source.startswith("env:"))


class Ambient(CredentialBase, frozen=True):
    """The host's default, untouched: the coding agent runs with the parent's environment
    (its credential variables included) and loads whatever it would load by itself.
    No guarantees, so no traits: a task that `requires` any is never run on it."""

    type: Literal["ambient"] = "ambient"
    isolate: bool = False


class Subscription(CredentialBase, frozen=True):
    """A stored login (Claude Pro/Max/Team/Enterprise, an omp or pi provider login).

    `config_dir`: the directory holding that login: Claude Code's `CLAUDE_CONFIG_DIR`,
    pi's agent directory (default: the user's own). `profile`: omp's profile holding it
    (default: the default profile).
    """

    type: Literal["subscription"] = "subscription"
    provider: str = "anthropic"
    config_dir: Path | None = None
    profile: str | None = None


class ApiKey(CredentialBase, frozen=True):
    """A provider's own API key, at the provider's own endpoint. Anything else is a `Gateway`."""

    type: Literal["api_key"] = "api_key"
    provider: str = "anthropic"
    key: SecretField


class OAuthToken(CredentialBase, frozen=True):
    """A long-lived OAuth token (`claude setup-token`)."""

    type: Literal["oauth_token"] = "oauth_token"
    provider: str = "anthropic"
    token: SecretField


class Gateway(CredentialBase, frozen=True):
    """Your own endpoint: an LLM gateway (LiteLLM and the like) or a self-hosted API.

    Claude Code speaks the Anthropic Messages API to `base_url`, sending `token`
    as a bearer token (`auth = "bearer"`) or as an API key (`auth = "api_key"`).
    omp addresses it as provider `provider` (models are `<provider>/<model>`;
    `litellm` by default), with `<PROVIDER>_BASE_URL` and the provider's key
    variable; pi as a provider of that name speaking the OpenAI chat-completions
    API to `base_url`. `headers` go on every request (Anthropic-API endpoints only).
    `base_url` may be `env:NAME` too, read when the launch is made.
    """

    type: Literal["gateway"] = "gateway"
    base_url: str
    token: SecretField | None = None
    auth: Literal["bearer", "api_key"] = "bearer"
    provider: str = "litellm"
    headers: dict[str, str] = Field(default_factory=dict)

    def endpoint(self, env: dict[str, str] | None) -> str:
        """`base_url`; an `env:NAME` reference is read from `env` (None: a check, nothing read)."""
        if not self.base_url.startswith("env:"):
            return self.base_url
        return Secret(self.base_url).resolve(env) if env is not None else "<unresolved>"

    def secret_sources(self) -> tuple[str, ...]:
        own = (self.base_url[4:],) if self.base_url.startswith("env:") else ()
        return super().secret_sources() + own

    def header_lines(self) -> str:
        """`ANTHROPIC_CUSTOM_HEADERS`: one `Name: value` per line."""
        return "\n".join(f"{k}: {v}" for k, v in self.headers.items())


class WorkloadIdentity(CredentialBase, frozen=True):
    """Anthropic workload identity federation: an identity token exchanged for API access."""

    type: Literal["workload_identity"] = "workload_identity"
    provider: str = "anthropic"
    federation_rule_id: str
    organization_id: str
    identity_token_file: Path
    service_account_id: str | None = None
    workspace_id: str | None = None


class Bedrock(CredentialBase, frozen=True):
    """Amazon Bedrock: an AWS profile (or the default chain), or a Bedrock API key (`bearer`)."""

    type: Literal["bedrock"] = "bedrock"
    region: str
    aws_profile: str | None = None
    bearer: SecretField | None = None


class Vertex(CredentialBase, frozen=True):
    """Google Vertex AI. `credentials_file` may be a service-account key or a workload
    identity federation (`external_account`) config."""

    type: Literal["vertex"] = "vertex"
    project: str
    region: str
    credentials_file: Path | None = None


class Pool(CredentialBase, frozen=True):
    """Several credentials used as one, e.g. two subscriptions or a set of OAuth tokens.

    `strategy`: `in_order` uses the first member that is not cooling down
    (the next one only after a 429); `round_robin` turns to the next member on
    every launch. A member that answers 429 cools down for the provider's stated
    retry-after, or `cooldown_s`; when every member is cooling, the launch is
    rate limited and the route's own failover takes over. A pool's traits are
    those every member carries, never declared on the pool itself.
    """

    type: Literal["pool"] = "pool"
    members: tuple[str, ...]
    strategy: Literal["in_order", "round_robin"] = "in_order"
    cooldown_s: float = 900.0


Credential = Annotated[
    Ambient | Subscription | ApiKey | OAuthToken | Gateway | WorkloadIdentity | Bedrock | Vertex | Pool, Field(discriminator="type")
]
CREDENTIAL_TYPES = ("ambient", "subscription", "api_key", "oauth_token", "gateway", "workload_identity", "bedrock", "vertex", "pool")
_ADAPTER: TypeAdapter = TypeAdapter(Credential)

AMBIENT = Ambient(name="ambient")


def parse_credentials(tables: dict[str, dict]) -> dict[str, CredentialBase]:
    """Every `[credentials.<name>]` table, pools resolved against their members."""
    out = {name: parse_credential(name, table) for name, table in tables.items()}
    for name, c in list(out.items()):
        if not isinstance(c, Pool):
            continue
        if c.traits:
            raise CredentialError(f"[credentials.{name}]: a pool's traits are its members' in common; put them on the members")
        if not c.members:
            raise CredentialError(f"[credentials.{name}]: a pool needs members")
        members = []
        for m in c.members:
            member = out.get(m)
            if member is None:
                raise CredentialError(f"[credentials.{name}]: no member [credentials.{m}]")
            if isinstance(member, Pool):
                raise CredentialError(f"[credentials.{name}]: member {m} is itself a pool")
            members.append(member)
        out[name] = c.model_copy(update={"traits": frozenset.intersection(*(m.traits for m in members))})
    return out


def parse_credential(name: str, table: dict) -> CredentialBase:
    """One `[credentials.<name>]` table."""
    data = {**table, "name": name}
    if "traits" in data:
        data["traits"] = frozenset(data["traits"])
    try:
        return _ADAPTER.validate_python(data)
    except Exception as exc:  # pydantic's message, with the table named
        raise CredentialError(f"[credentials.{name}]: {exc}") from None


# --- what a backend makes of one ---------------------------------------------


def model_provider(model: str) -> str:
    """The provider a provider-qualified model names (`anthropic` of `anthropic/claude-haiku-5-5`);
    '' for a bare model id."""
    return model.split("/", 1)[0] if "/" in model else ""


def model_id(model: str) -> str:
    """The model id within its provider (`claude-haiku-5-5` of `anthropic/claude-haiku-5-5`)."""
    return model.split("/", 1)[1] if "/" in model else model


def check_provider(credential: CredentialBase, model: str, provider: str, named: str = "") -> None:
    """Refuse a credential for `provider` on a model of another provider. `named`: the provider
    the credential names, when the agent knows its login under another (`provider`)."""
    wanted = model_provider(model)
    if wanted and provider and provider != wanted:
        what = provider if not named or named == provider else f"{provider} (its {named} login)"
        raise CredentialError(f"model {model} is a {wanted} model; credential {credential.label} is for {what}")


def key_var(provider: str, special: dict[str, str] | None = None) -> str:
    """The variable a coding agent reads `provider`'s API key from: `special`'s name for it,
    else `<PROVIDER>_API_KEY` (omp and pi alike)."""
    return (special or {}).get(provider) or provider.upper().replace("-", "_").replace(".", "_") + "_API_KEY"


def secret_value(secret: Secret, env: dict[str, str] | None) -> str:
    """`secret` resolved against `env`; a placeholder when `env` is None (a check reads no secret)."""
    return secret.resolve(env) if env is not None else "<unresolved>"


@dataclass(frozen=True)
class CredentialBinding:
    """How one backend uses one credential for one launch.

    `env` is added to the child's environment after every credential-selecting
    variable has been removed (`scrubbed`); `args` go on its command line and
    never hold a secret. `isolated` is True when the backend can guarantee that
    nothing it loads by default is used instead; `isolation` says how, or why not.
    """

    env: dict[str, str] = field(default_factory=dict)
    args: tuple[str, ...] = ()
    isolated: bool = False
    isolation: str = ""


#: Every credential-selecting variable a supported coding agent reads. Removed
#: from every child before the chosen credential is applied, so a key left in
#: the parent's environment can never move the bill elsewhere.
SENSITIVE = (
    # Anthropic direct, gateways, OAuth, profiles and federation
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_OAUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_PROFILE",
    "ANTHROPIC_CONFIG_DIR",
    "ANTHROPIC_FEDERATION_RULE_ID",
    "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_IDENTITY_TOKEN",
    "ANTHROPIC_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_SERVICE_ACCOUNT_ID",
    "ANTHROPIC_WORKSPACE_ID",
    # cloud providers
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_USE_MANTLE",
    "AWS_BEARER_TOKEN_BEDROCK",
    "AWS_PROFILE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "CLOUD_ML_REGION",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "ANTHROPIC_FOUNDRY_API_KEY",
    "ANTHROPIC_FOUNDRY_AUTH_TOKEN",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_FOUNDRY_RESOURCE",
    # where a coding agent keeps its own logins
    "CLAUDE_CONFIG_DIR",
    "OMP_PROFILE",
    "OPENCODE_AUTH_CONTENT",
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_CONTENT",
    "OPENCODE_CONFIG_DIR",
    "PI_CODING_AGENT_DIR",
    "CODEX_HOME",
    # Codex
    "CODEX_API_KEY",
    "CODEX_ACCESS_TOKEN",
    # other providers omp can use
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "AZURE_OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_CLOUD_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENCODE_API_KEY",
    "OPENCODE_GO_API_KEY",
    "OPENCODE_GO_BASE_URL",
    "LITELLM_API_KEY",
    "LITELLM_BASE_URL",
    "GROQ_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "CEREBRAS_API_KEY",
    "ZAI_API_KEY",
    "COPILOT_GITHUB_TOKEN",
    "KILO_API_KEY",
    "MINIMAX_API_KEY",
)


#: Names that look like a secret whatever they belong to. omp, for one, turns on
#: a provider for any `<PROVIDER>_API_KEY` it finds, so a list of known names
#: alone would let an unknown key through. A tool that needs one of these (a
#: search API key, say) gets it back explicitly through the launch's `env`.
SECRET_NAME_RE = re.compile(r"(_API_KEY|_AUTH_TOKEN|_OAUTH_TOKEN|_ACCESS_TOKEN|_SECRET_ACCESS_KEY|_SESSION_TOKEN)$")


def child_env(
    base: dict[str, str],
    credential: CredentialBase,
    binding: CredentialBinding,
    launch_env: dict[str, str],
    *,
    drop: tuple[str, ...] = (),
    defaults: dict[str, str] | None = None,
) -> dict[str, str]:
    """A coding agent's environment for one launch.

    `ambient` keeps the host's default: the parent environment as it is (minus
    `drop`, the agent's own parent-session variables), then `launch_env`. Any
    other credential is the only one the child can see: every credential-selecting
    or secret-looking variable is removed (and the credential's own secret
    sources), `launch_env` is added without credential variables, and the binding
    is applied last, so nothing can override it.
    """
    if isinstance(credential, Ambient):
        kept = {k: v for k, v in base.items() if k not in drop}
        return {**kept, **(defaults or {}), **launch_env, **binding.env}
    extra = {k: v for k, v in launch_env.items() if k not in SENSITIVE}
    return {**scrubbed(base, drop + credential.secret_sources()), **(defaults or {}), **extra, **binding.env}


def scrubbed(base: dict[str, str], extra: tuple[str, ...] = ()) -> dict[str, str]:
    """`base` minus every credential-selecting or secret-looking variable (and `extra`)."""
    drop = set(SENSITIVE) | set(extra)
    return {k: v for k, v in base.items() if k not in drop and not SECRET_NAME_RE.search(k)}
