FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY proseforge ./proseforge
RUN python -m pip install --no-cache-dir -e ".[api,dev,legacy]"
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
