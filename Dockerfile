FROM python:3.11-slim

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY data/reduced_embeddings.npy data/reduced_embeddings.npy
COPY data/embedding_ids.csv data/embedding_ids.csv

ENV PORT=10000
EXPOSE 10000

CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT
