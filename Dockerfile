# syntax=docker/dockerfile:1

# --- Stage 1: build the virtualenv from the pinned requirements ---
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt


# --- Stage 2: runtime image carrying only the venv and application code ---
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY contracts/ ./contracts/
COPY src/ ./src/
COPY api/ ./api/
COPY apps/ ./apps/

RUN useradd --create-home --uid 10000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8501

# Default process is the FastAPI gateway; the UI service overrides this command.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
