"""
Comprehensive Performance Benchmarking & Capacity Testing Suite
Earth Intelligence Digital Twin (EIDT) - Maharashtra
Phase 7L: Latency, Throughput & Scalability Profiling.

Measures:
  - Median (p50), 95th percentile (p95), and 99th percentile (p99) latencies.
  - Request throughput (requests per second).
  - Error rates across primary regional and emergency endpoints.
  - Viewport-bounded geographic query performance vs unconstrained statewide queries.
"""

import os
import sys
import time
import json
import statistics
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ENDPOINTS_TO_BENCHMARK = [
    {
        "name": "Statewide Study Areas",
        "method": "GET",
        "url": "/api/study-areas",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Viewport Bounded Wards (MMR Bbox)",
        "method": "GET",
        "url": "/api/study-areas?min_lat=18.9&min_lon=72.8&max_lat=19.3&max_lon=73.0",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Multi-Scale GeoJSON (Zoom Level 7)",
        "method": "GET",
        "url": "/api/study-areas/geojson?zoom=7",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Multi-Hazard Platform Status",
        "method": "GET",
        "url": "/api/hazards",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Emergency Facilities Retrieval",
        "method": "GET",
        "url": "/api/emergency/facilities?limit=50",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Emergency Evacuation Routing",
        "method": "POST",
        "url": "/api/routing/route",
        "payload": {
            "origin_lat": 19.0688,
            "origin_lon": 72.8710,
            "destination_lat": 19.0390,
            "destination_lon": 72.8619,
            "routing_mode": "emergency_vehicle"
        },
        "iterations": 20
    },
    {
        "name": "Historical Disaster Event Catalogue",
        "method": "GET",
        "url": "/api/validation/events",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Regional Ingestion Statewide Summary",
        "method": "GET",
        "url": "/api/regional-ingestion/summary",
        "payload": None,
        "iterations": 25
    },
    {
        "name": "Data Readiness Probe",
        "method": "GET",
        "url": "/api/health/data-readiness",
        "payload": None,
        "iterations": 25
    }
]


def benchmark_single_endpoint(endpoint_cfg: Dict[str, Any]) -> Dict[str, Any]:
    name = endpoint_cfg["name"]
    method = endpoint_cfg["method"]
    url = endpoint_cfg["url"]
    payload = endpoint_cfg["payload"]
    iterations = endpoint_cfg["iterations"]

    durations_ms = []
    errors = 0

    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            if method == "GET":
                resp = client.get(url)
            elif method == "POST":
                resp = client.post(url, json=payload)
            else:
                resp = client.get(url)

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if resp.status_code >= 400:
                errors += 1
            durations_ms.append(elapsed_ms)
        except Exception:
            errors += 1
            durations_ms.append((time.perf_counter() - t0) * 1000.0)

    durations_ms.sort()
    p50 = statistics.median(durations_ms)
    p95 = durations_ms[int(len(durations_ms) * 0.95)] if len(durations_ms) > 1 else durations_ms[0]
    p99 = durations_ms[-1]

    return {
        "endpoint": name,
        "method": method,
        "url": url,
        "samples": len(durations_ms),
        "errors": errors,
        "error_rate_pct": round((errors / len(durations_ms)) * 100.0, 2),
        "mean_ms": round(statistics.mean(durations_ms), 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "min_ms": round(min(durations_ms), 2),
        "max_ms": round(max(durations_ms), 2)
    }


def run_concurrency_stress_test(concurrency: int = 20, total_requests: int = 100) -> Dict[str, Any]:
    """Tests system throughput under concurrent asynchronous load."""
    urls = [
        "/api/health/live",
        "/api/health/ready",
        "/api/study-areas",
        "/api/regional-ingestion/summary",
        "/api/emergency/facilities"
    ]

    t0 = time.perf_counter()
    errors = 0
    completed = 0

    def make_req(idx: int):
        target = urls[idx % len(urls)]
        res = client.get(target)
        return res.status_code

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_req, i) for i in range(total_requests)]
        for f in futures:
            try:
                code = f.result()
                if code >= 400:
                    errors += 1
                completed += 1
            except Exception:
                errors += 1

    total_time_s = time.perf_counter() - t0
    rps = round(completed / total_time_s, 2) if total_time_s > 0 else 0

    return {
        "concurrency_level": concurrency,
        "total_requests": completed,
        "total_time_seconds": round(total_time_s, 3),
        "throughput_req_per_sec": rps,
        "errors": errors,
        "error_rate_pct": round((errors / completed) * 100.0, 2) if completed > 0 else 0.0
    }


def run_full_benchmark_suite():
    print("=========================================================================")
    print("EIDT Maharashtra — Capacity & Performance Benchmark Suite")
    print("=========================================================================")

    results = []
    print("\n[1/2] Profiling Endpoint Latencies (p50, p95, p99)...")
    for cfg in ENDPOINTS_TO_BENCHMARK:
        res = benchmark_single_endpoint(cfg)
        results.append(res)
        print(f"  * {res['endpoint']:<35} | p50: {res['p50_ms']:>6.2f}ms | p95: {res['p95_ms']:>6.2f}ms | p99: {res['p99_ms']:>6.2f}ms | Errors: {res['errors']}")

    print("\n[2/2] Running Concurrency Stress Test...")
    stress = run_concurrency_stress_test(concurrency=15, total_requests=90)
    print(f"  * Concurrency: {stress['concurrency_level']} workers")
    print(f"  * Total requests: {stress['total_requests']}")
    print(f"  * Throughput: {stress['throughput_req_per_sec']} requests/sec")
    print(f"  * Total execution time: {stress['total_time_seconds']}s")
    print(f"  * Error rate: {stress['error_rate_pct']}%")

    report = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": "FastAPI + PostgreSQL / SQLite Fallback + GeoPandas/Shapely",
        "benchmark_results": results,
        "concurrency_stress_test": stress
    }

    report_path = os.path.join(os.path.dirname(__file__), "..", "docs", "BENCHMARK_REPORT.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Benchmark completed. Empirical metrics saved to {report_path}")
    return report


if __name__ == "__main__":
    run_full_benchmark_suite()
