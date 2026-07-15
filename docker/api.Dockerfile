FROM python:3.12-slim

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
COPY proseforge ./proseforge
RUN python -m pip install --no-cache-dir -e ".[api]"
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint-api.sh"]
CMD ["uvicorn", "proseforge.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
