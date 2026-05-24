FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_VERSION=22

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY frontend ./frontend

WORKDIR /app/frontend
RUN npm install

WORKDIR /app
EXPOSE 7860

CMD ["sh", "-c", "cd /app/frontend && npm run dev -- --host 127.0.0.1 --port 5173 & cd /app && python -m uvicorn api.main:app --host 0.0.0.0 --port 7860"]
