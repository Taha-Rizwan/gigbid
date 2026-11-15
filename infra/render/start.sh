#!/bin/sh
# API (one process) on 127.0.0.1:8000; the web server on Render's $PORT proxies /api to it.
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --workers 1 &
cd web && PORT="${PORT:-10000}" HOSTNAME=0.0.0.0 exec node server.js
