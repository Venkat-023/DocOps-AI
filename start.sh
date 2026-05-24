#!/bin/sh
set -eu

cd /app/frontend
npm run dev -- --host 127.0.0.1 --port 5173 &

cd /app
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-7860}"
