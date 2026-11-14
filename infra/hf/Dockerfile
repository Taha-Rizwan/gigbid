# All-in-one image for a Hugging Face Docker Space (free CPU tier: no Docker Compose there).
# Same code and services as infra/docker-compose.yml; supervisord runs them in one container.
# Postgres (Neon) and Redis (Upstash) are external, configured through Space secrets.
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
ENV API_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    HOME=/home/user PATH=/app/.venv/bin:$PATH
RUN useradd -m -u 1000 user && pip install --no-cache-dir uv==0.13.8 supervisor==4.3.0
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
COPY infra/hf/supervisord.conf /etc/supervisord.conf
# bake the CPU embedding + reranker models into the image (no download at start-up)
RUN mkdir -p data/cache && python -c "from rag.index.embeddings import _embedder, _reranker; from agent.settings import config; m=config()['models']; _embedder(m['embeddings']); _reranker(m['reranker'])" \
    && chown -R user:user /app
USER user
ENV GIGSIM_SEED_DIR=/app/data/deploy_seed GIGSIM_DB=/tmp/gigsim.sqlite GIGSIM_CLOCK_SPEED=10 \
    GIGSIM_BASE_URL=http://127.0.0.1:8081 MCP_HOST=127.0.0.1 APP_ENV=production
EXPOSE 7860
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
