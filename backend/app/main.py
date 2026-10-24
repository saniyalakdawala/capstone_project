import os
import time
import uuid
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.routers import (
    health, study_areas, weather, infrastructure, flood_events,
    scenarios, analytics, models_eval, data_pipeline, flood, inundation, hazards,
    routing, emergency, evacuation, monitoring, alerts, validation, replay, regional_ingestion
)
from app.services.scheduler_service import get_orchestration_scheduler
from app.database import SessionLocal
from app.models.schema import ApiMetricLog

logger = logging.getLogger("eidt.api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Regional Earth Intelligence Digital Twin for Multi-Hazard Disaster Intelligence in Maharashtra, India",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 1. Observability & Correlation ID Middleware
class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract or generate X-Correlation-ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start_time = time.time()
        response: Response = None

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Unhandled exception [CID: {correlation_id}] on {request.method} {request.url.path}: {exc}", exc_info=True)
            self._log_metric(request, 500, duration_ms, correlation_id)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal server error occurred.",
                    "correlation_id": correlation_id,
                    "error_code": "INTERNAL_SERVER_ERROR"
                },
                headers={"X-Correlation-ID": correlation_id}
            )

        duration_ms = (time.time() - start_time) * 1000.0
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

        # Failsafe metric recording (skip high-frequency docs/favicon)
        path = request.url.path
        if not (path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi.json")):
            self._log_metric(request, response.status_code, duration_ms, correlation_id)

        return response

    def _log_metric(self, request: Request, status_code: int, duration_ms: float, correlation_id: str):
        try:
            db = SessionLocal()
            try:
                log_entry = ApiMetricLog(
                    log_id=str(uuid.uuid4()),
                    correlation_id=correlation_id,
                    endpoint=request.url.path[:255],
                    method=request.method[:16],
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    user_agent=(request.headers.get("user-agent") or "")[:500],
                    client_ip=request.client.host if request.client else None
                )
                db.add(log_entry)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            # Observability logging should never crash the primary request
            logger.debug(f"Metrics logging skipped: {e}")

app.add_middleware(ObservabilityMiddleware)

# 2. CORS configuration with environment control
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    scheduler = get_orchestration_scheduler()
    scheduler.start()
    logger.info("EIDT Maharashtra Digital Twin API started successfully.")

@app.on_event("shutdown")
def shutdown_event():
    scheduler = get_orchestration_scheduler()
    scheduler.shutdown()
    logger.info("EIDT Maharashtra Digital Twin API shutdown clean.")

# Include Routers under /api
api_prefix = settings.API_V1_STR
app.include_router(health.router, prefix=api_prefix)
app.include_router(study_areas.router, prefix=api_prefix)
app.include_router(regional_ingestion.router, prefix=api_prefix)
app.include_router(validation.router, prefix=api_prefix)
app.include_router(replay.router, prefix=api_prefix)
app.include_router(monitoring.router, prefix=api_prefix)
app.include_router(alerts.router, prefix=api_prefix)
app.include_router(hazards.router, prefix=api_prefix)
app.include_router(routing.router, prefix=api_prefix)
app.include_router(emergency.router, prefix=api_prefix)
app.include_router(evacuation.router, prefix=api_prefix)
app.include_router(flood.router, prefix=api_prefix)
app.include_router(inundation.router, prefix=api_prefix)
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
        "study_region": "Maharashtra, India"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
