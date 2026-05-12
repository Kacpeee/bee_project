FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY ingest_data.py ./

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "ingest_data.py"]
