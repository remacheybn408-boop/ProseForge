FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY proseforge ./proseforge
RUN python -m pip install --no-cache-dir -e ".[api,worker]"
COPY . .

RUN addgroup --system --gid 10001 proseforge \
    && adduser --system --uid 10001 --ingroup proseforge proseforge \
    && mkdir -p /data/blobs /data/backups \
    && chown -R proseforge:proseforge /app /data

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER proseforge
ENTRYPOINT ["/app/docker/entrypoint-worker.sh"]
