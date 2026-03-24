FROM python:3.11-slim

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY data/processed/papers_clustered.csv data/processed/papers_clustered.csv
COPY data/processed/embedding_ids.csv data/embedding_ids.csv
COPY data/reduced_embeddings.npy data/reduced_embeddings.npy

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
