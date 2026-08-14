FROM ghcr.io/astral-sh/uv:0.12.3 AS uv

FROM python:3.12-slim-bookworm AS base

COPY --from=uv /uv /uvx /bin/

ENV PATH="/opt/cadmus-venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/cadmus-venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/backend/pyproject.toml packages/backend/pyproject.toml
COPY apps/api/src apps/api/src
COPY apps/worker/src apps/worker/src
COPY packages/backend/src packages/backend/src
COPY alembic.ini alembic.ini
COPY migrations migrations

RUN uv sync --all-packages --locked --no-dev \
    && useradd --create-home --uid 10001 cadmus

FROM python:3.12-slim-bookworm AS test

COPY --from=uv /uv /uvx /bin/

ENV PATH="/opt/cadmus-venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/cadmus-venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/backend/pyproject.toml packages/backend/pyproject.toml
COPY apps/api/src apps/api/src
COPY apps/worker/src apps/worker/src
COPY packages/backend/src packages/backend/src
COPY apps/api/tests apps/api/tests
COPY apps/worker/tests apps/worker/tests
COPY packages/backend/tests packages/backend/tests
COPY tests tests
COPY fixtures fixtures
COPY alembic.ini alembic.ini
COPY migrations migrations

RUN uv sync --all-packages --locked \
    && useradd --create-home --uid 10001 cadmus

USER cadmus

FROM base AS runtime

USER cadmus

EXPOSE 8000

CMD ["uvicorn", "cadmus_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
