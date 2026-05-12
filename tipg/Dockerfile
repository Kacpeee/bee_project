FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "tipg.main:app", "--host", "0.0.0.0", "--port", "8083"]
