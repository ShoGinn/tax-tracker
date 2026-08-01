FROM node:26-bookworm-slim AS frontend-build

WORKDIR /app/frontend

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build


FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn taxtracker.cli.app:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
