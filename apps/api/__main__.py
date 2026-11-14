"""python -m apps.api  (local dev; production uses uvicorn directly on Linux)."""

import os

from apps.api.main import app
from common import serve

serve(app, os.environ.get("API_HOST", "127.0.0.1"), int(os.environ.get("API_PORT", 8000)))
