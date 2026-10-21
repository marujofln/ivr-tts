FROM python:3.12-slim

EXPOSE 8000

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  UV_PROJECT_ENVIRONMENT=/usr/local \
  UV_COMPILE_BYTECODE=1

# uv is the package manager: copy the static binary from the official image
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /bin/

WORKDIR /opt/ivr-tts

# Install dependencies first to cache them in a docker layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . /opt/ivr-tts/

# Runs as the same UID as the host freeswitch user, so mounted volumes keep permissions
RUN adduser -u 995 --disabled-password --gecos "" freeswitch && chown -R freeswitch /opt/ivr-tts
USER freeswitch

# Settings are read from /opt/ivr-tts/etc/.env (mount it as a volume) or from environment variables
CMD ["./run.sh"]
