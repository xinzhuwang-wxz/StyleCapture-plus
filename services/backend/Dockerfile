FROM ghcr.io/astral-sh/uv:0.8-python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

ARG INSTALL_AI_LIGHT=false

COPY .python-version pyproject.toml uv.lock ./
COPY services/backend services/backend
COPY config config
RUN if [ "$INSTALL_AI_LIGHT" = "true" ]; then \
      uv sync --frozen --no-dev --package stylecapture-backend --extra ai-light; \
    else \
      uv sync --frozen --no-dev --package stylecapture-backend; \
    fi

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/services/backend/src"

CMD ["uvicorn", "stylecapture_backend.entrypoint:build_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
