FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy HF_HUB_DISABLE_SYMLINKS_WARNING=1
RUN pip install --no-cache-dir uv==0.13.8
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY agent ./agent
COPY rag ./rag
COPY common ./common
COPY mcp_servers ./mcp_servers
COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api
COPY worker ./worker
COPY gigsim ./gigsim
COPY evals/__init__.py ./evals/__init__.py
COPY data/personas ./data/personas
COPY data/policy_pack ./data/policy_pack
COPY data/deploy_seed ./data/deploy_seed
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
ENV MCP_HOST=0.0.0.0
EXPOSE 8102
CMD ["python", "-m", "mcp_servers.portfolio.server"]
