# LLM Research Trend Visualizer

A full-stack application for analyzing and visualizing citation trends in LLM research papers across top AI venues (NeurIPS, ICML, ICLR, CVPR, ACL, etc.).

## Features

- **Cluster Visualization** — Papers grouped by research topic using embedding-based clustering
- **Trend Analysis** — Track rising and declining research trends over time
- **Paper Discovery** — Natural language search using cosine similarity + keyword matching
- **Venue Exploration** — Browse papers by conference/venue and year
- **Recommendations** — Get similar paper suggestions based on your interests

## Tech Stack

- **Frontend**: Vanilla JS + HTML/CSS (served by FastAPI)
- **Backend**: Python / FastAPI
- **Pipeline**: Semantic Scholar API → sentence-transformers → UMAP → HDBSCAN

## Local Development

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/citation-analysis.git
cd citation-analysis

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# 5. Run the data pipeline (if no pre-built static data)
# python -m pipeline.<step>  (see pipeline/ directory)

# 6. Start the server
uvicorn backend.main:app --reload

# 7. Open http://localhost:8000
```

## Deployment (Render)

This project includes a `Dockerfile` and `render.yaml` for one-click deployment on [Render](https://render.com):

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
3. Connect your GitHub repo — Render will auto-detect `render.yaml`
4. Set environment variables in Render dashboard (see `.env.example`)
5. Deploy

The FastAPI backend serves both the API and the frontend static files, so a single service handles everything.

## Project Structure

```
├── backend/           # FastAPI application
│   ├── main.py        # App entry point, mounts routers & static files
│   ├── data_store.py  # Data loading utilities
│   ├── trend_logic.py # Trend computation logic
│   ├── routers/       # API route handlers
│   └── static/        # Pre-computed JSON data served at runtime
├── frontend/          # Static frontend (HTML/JS/CSS)
├── pipeline/          # Data collection & processing scripts
├── data/              # Raw/processed data (gitignored)
├── Dockerfile
├── render.yaml
└── requirements.txt
```

## License

MIT
