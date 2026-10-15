# syntax=docker/dockerfile:1
# The contraagent hub as a container image. The build context is the repository root:
#
#   docker build -f src/contraagent/docs/examples/hub/Dockerfile -t contraagent-hub .
#
# (compose.yaml beside this file builds it the same way). Dockerfile.dockerignore lists
# what enters the context: pyproject.toml, uv.lock, LICENSE and src/. The monitor's UI is
# committed in src/contraagent/_internal/monitor/static, so no Node build runs here.
#
# The hub runs as the user `contraagent` (uid 10001). /data is its volume: the open
# transcript segments go to /data/streams. Tokens are files, mounted read-only at
# /run/secrets (compose secrets), and named with --ingest-token-file and --read-token-file.

FROM ghcr.io/astral-sh/uv:0.11.18 AS uv

FROM python:3.12.12-slim-bookworm AS build
COPY --from=uv /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /src
COPY pyproject.toml uv.lock LICENSE ./
# The locked dependencies first, in a layer of their own that a source change keeps.
RUN uv sync --frozen --no-dev --extra hub --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --extra hub --no-editable

FROM python:3.12.12-slim-bookworm
RUN groupadd --system --gid 10001 contraagent \
    && useradd --system --uid 10001 --gid contraagent --home-dir /data --no-create-home contraagent \
    && mkdir /data \
    && chown contraagent:contraagent /data
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1
USER contraagent
WORKDIR /data
VOLUME /data
EXPOSE 8790
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8790/healthz', timeout=4)"]
ENTRYPOINT ["contraagent", "hub"]
CMD ["--host", "0.0.0.0", "--streams-dir", "/data/streams", \
     "--ingest-token-file", "/run/secrets/ingest-tokens", "--read-token-file", "/run/secrets/read-token"]
