from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.routers import (
    health, study_areas, weather, infrastructure, flood_events,
    scenarios, analytics, models_eval, data_pipeline
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Regional Earth Intelligence Digital Twin for Flood Risk & Scenario Simulation in Mumbai, Maharashtra",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup for React Vite Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers under /api
api_prefix = settings.API_V1_STR
app.include_router(health.router, prefix=api_prefix)
app.include_router(study_areas.router, prefix=api_prefix)
app.include_router(weather.router, prefix=api_prefix)
app.include_router(infrastructure.router, prefix=api_prefix)
app.include_router(flood_events.router, prefix=api_prefix)
app.include_router(scenarios.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)
app.include_router(models_eval.router, prefix=api_prefix)
app.include_router(data_pipeline.router, prefix=api_prefix)

# Serve static data files (GeoJSON, rasters, etc.)
if os.path.exists(settings.DATA_DIR):
    app.mount("/static/data", StaticFiles(directory=settings.DATA_DIR), name="static-data")

@app.get("/")
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "api_docs": "/docs",
        "study_region": "Mumbai, Maharashtra, India"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
