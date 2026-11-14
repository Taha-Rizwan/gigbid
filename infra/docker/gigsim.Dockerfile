FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic pyyaml python-dotenv
COPY gigsim ./gigsim
COPY data/deploy_seed ./data/deploy_seed
ENV GIGSIM_SEED_DIR=/app/data/deploy_seed GIGSIM_DB=/data/gigsim.sqlite
EXPOSE 8081
CMD ["uvicorn", "gigsim.app:app", "--host", "0.0.0.0", "--port", "8081"]
