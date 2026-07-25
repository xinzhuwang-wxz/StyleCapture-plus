FROM ghcr.io/astral-sh/uv:0.8-python3.12-bookworm-slim@sha256:1e63e300ec9908733d44d2eaa37688dd2c51fc7c1350f8fd046413d05f21486c

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

ARG INSTALL_AI_LIGHT=false
ARG INSTALL_GATEWAY=false
ARG UV_DEFAULT_INDEX=https://pypi.org/simple
ARG UV_INSECURE_HOST=

ENV UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX} \
    UV_INSECURE_HOST=${UV_INSECURE_HOST}

COPY .python-version pyproject.toml uv.lock ./
COPY services/backend/pyproject.toml services/backend/pyproject.toml
RUN if [ "$INSTALL_GATEWAY" = "true" ]; then \
      uv sync --frozen --no-dev --package stylecapture-backend --extra gateway --no-install-workspace; \
    elif [ "$INSTALL_AI_LIGHT" = "true" ]; then \
      uv sync --frozen --no-dev --package stylecapture-backend --extra ai-light --no-install-workspace; \
    else \
      uv sync --frozen --no-dev --package stylecapture-backend --no-install-workspace; \
    fi

COPY services/backend services/backend
COPY config config
RUN if [ "$INSTALL_GATEWAY" = "true" ]; then \
      uv sync --frozen --no-dev --package stylecapture-backend --extra gateway; \
    elif [ "$INSTALL_AI_LIGHT" = "true" ]; then \
      uv sync --frozen --no-dev --package stylecapture-backend --extra ai-light; \
    else \
      uv sync --frozen --no-dev --package stylecapture-backend; \
    fi

RUN groupadd --system stylecapture \
    && useradd --system --gid stylecapture --home-dir /home/stylecapture --create-home stylecapture \
    && mkdir -p /data/uploads /home/stylecapture/.cache/huggingface \
    && chown -R stylecapture:stylecapture /data/uploads /home/stylecapture

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/services/backend/src" \
    XDG_CACHE_HOME="/home/stylecapture/.cache"

USER stylecapture

CMD ["uvicorn", "stylecapture_backend.entrypoint:build_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
