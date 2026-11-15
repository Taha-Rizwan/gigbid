# Single-container image for Render's free tier (512 MB): one Python process (API + in-process MCP
# servers + GigSim mounted at /gigsim + inline worker) and the Next.js server. Postgres (Neon) and
# Redis are external. The full multi-service layout is infra/docker-compose.yml.
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
RUN mkdir -p public
ENV API_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    MALLOC_ARENA_MAX=2 PATH=/app/.venv/bin:$PATH
RUN pip install --no-cache-dir uv==0.13.8
COPY --from=web /usr/local/bin/node /usr/local/bin/node
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
COPY --from=web /web/.next/standalone ./web
COPY --from=web /web/.next/static ./web/.next/static
COPY --from=web /web/public ./web/public
COPY infra/render/start.sh ./start.sh
RUN mkdir -p data/cache && python -c "from rag.index.embeddings import _embedder, _reranker; from agent.settings import config; m=config()['models']; _embedder(m['embeddings'])"
ENV GIGBID_INPROCESS_MCP=1 GIGSIM_MOUNT=1 WORKER_MODE=inline GIGSIM_BASE_URL=http://127.0.0.1:8000/gigsim \
    GIGSIM_SEED_DIR=/app/data/deploy_seed GIGSIM_DB=/tmp/gigsim.sqlite GIGSIM_LLM_DISABLED=1 APP_ENV=production \
    RAG_VARIANT=v2_hybrid EMBED_THREADS=1 OMP_NUM_THREADS=1
CMD ["sh", "start.sh"]
