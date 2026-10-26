FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_NO_CACHE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY app ./app
COPY eval ./eval
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/cache/huggingface LABDOCS_UPLOAD_DIR=/app/data/uploads
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/cache/huggingface /app/data/uploads \
    && chown -R appuser:appuser /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser eval ./eval
COPY --chown=appuser:appuser data/sample ./data/sample
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]

# Explicit test image; production runtime contains no test factory or fixed keys.
FROM runtime AS browser-test
COPY --chown=appuser:appuser tests/__init__.py tests/helpers.py ./tests/
COPY --chown=appuser:appuser frontend/e2e/server.py ./frontend/e2e/server.py

FROM runtime AS production
