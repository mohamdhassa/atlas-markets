FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY app /app/app
COPY tests /app/tests
COPY docker-compose.oracle.yml /app/docker-compose.oracle.yml
COPY .env.oracle.example /app/.env.oracle.example

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
