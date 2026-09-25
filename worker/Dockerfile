FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENHANDS_SUPPRESS_BANNER=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY ../backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ../backend /app

CMD ["python", "-m", "app.runtime.lifecycle"]
