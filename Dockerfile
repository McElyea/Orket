FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORKET_HOST=0.0.0.0 \
    ORKET_PORT=8082

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY orket ./orket
COPY server.py main.py ./

RUN python -m pip install --upgrade pip && python -m pip install .

RUN useradd --create-home --shell /bin/bash orket
USER orket

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://127.0.0.1:8082/health || exit 1

CMD ["python", "server.py"]
