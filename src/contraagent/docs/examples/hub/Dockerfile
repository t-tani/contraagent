# syntax=docker/dockerfile:1
# The contraagent hub as a container image, installed from PyPI or from a wheel. The build
# context is this directory; compose.yaml beside this file builds it with these arguments:
#
#   CONTRAAGENT_VERSION  the version to install (`contraagent --version` prints the installed one)
#   CONTRAAGENT_WHEEL    a wheel file in this directory, installed in place of PyPI's (optional)
#
#   docker build --build-arg CONTRAAGENT_VERSION=<version> -t contraagent-hub:<version> .
#
# The image holds the version it was asked for, or the build fails. .dockerignore lets only
# wheels into the context.
#
# The hub runs as the user `contraagent` (uid 10001). /data is its volume: the open
# transcript segments go to /data/streams. Tokens are files, mounted read-only at
# /run/secrets (compose secrets), and named with --ingest-token-file and --read-token-file.

FROM python:3.12.12-slim-bookworm AS build
ARG CONTRAAGENT_VERSION
ARG CONTRAAGENT_WHEEL=
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN --mount=type=bind,target=/context \
    if [ -z "$CONTRAAGENT_VERSION" ]; then echo "set the build argument CONTRAAGENT_VERSION" >&2; exit 1; fi \
    && if [ -n "$CONTRAAGENT_WHEEL" ]; then spec="/context/$CONTRAAGENT_WHEEL[hub]"; \
       else spec="contraagent[hub]==$CONTRAAGENT_VERSION"; fi \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --compile "$spec" \
    && installed=$(/opt/venv/bin/contraagent --version) \
    && if [ "$installed" != "contraagent $CONTRAAGENT_VERSION" ]; then \
         echo "installed $installed, not contraagent $CONTRAAGENT_VERSION (CONTRAAGENT_VERSION)" >&2; exit 1; fi

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
