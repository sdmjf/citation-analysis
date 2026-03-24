from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.data_store import load_clusters, load_text_search_assets
from backend.routers import clusters, papers, recommendations, trends


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="LLM Research Trend Visualizer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clusters.router)
app.include_router(trends.router)
app.include_router(papers.router)
app.include_router(recommendations.router)

app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="frontend-assets")
app.mount("/static", StaticFiles(directory=BASE_DIR / "backend" / "static"), name="data-static")


@app.on_event("startup")
def warm_search_assets():
    load_text_search_assets()


@app.get("/api/health")
def health():
    return {"status": "ok", "clusters": len(load_clusters())}


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
