FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

FROM base AS development

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests

FROM base AS production

# Render and other PaaS providers expose the HTTP port through $PORT.
CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
