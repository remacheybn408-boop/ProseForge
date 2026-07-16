FROM python:3.12-slim

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
COPY proseforge ./proseforge
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ".[api]"
COPY . .

RUN addgroup --system --gid 10001 proseforge \
    && adduser --system --uid 10001 --ingroup proseforge proseforge \
    && mkdir -p /data/blobs /data/backups \
    && chown -R proseforge:proseforge /app /data

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
USER proseforge
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint-api.sh"]
CMD ["uvicorn", "proseforge.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
