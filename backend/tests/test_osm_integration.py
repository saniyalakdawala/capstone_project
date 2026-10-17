import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.ingestion.osm_pipeline import OSMRealDataIngestionPipeline
from app.database import SessionLocal
from app.models.schema import RoadSegment, Infrastructure

client = TestClient(app)

def test_osm_status_endpoint():
    """Verify that OpenStreetMap data status endpoint returns real provenance metadata."""
    res = client.get("/api/infrastructure/osm/status")
    assert res.status_code == 200
    data = res.json()
    
    assert data["source_name"] == "OpenStreetMap"
    assert data["status"] == "SUCCESS_REAL_DATA"
    assert "EPSG:4326" in data["crs"]
    assert "OpenStreetMap contributors" in data["attribution"]
    assert data["features_retrieved"]["road_segments_count"] > 0
    assert data["features_retrieved"]["database_roads_persisted"] > 0
    assert data["errors"] is None

def test_osm_roads_geojson_endpoint():
    """Verify that the road GeoJSON endpoint returns valid LineString features with attribution."""
    res = client.get("/api/infrastructure/roads/geojson?limit=50")
    assert res.status_code == 200
    data = res.json()
    
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    
    first_feat = data["features"][0]
    assert first_feat["geometry"]["type"] in ["LineString", "MultiLineString"]
    props = first_feat["properties"]
    assert "road_class" in props
    assert "vulnerability_index" in props
    assert "attribution" in props

def test_osm_roads_bbox_filtering():
    """Verify spatial filtering for a requested map area bounding box."""
    # Query a sub-corridor within Kurla
    res = client.get("/api/infrastructure/roads/geojson?min_lon=72.860&min_lat=19.060&max_lon=72.875&max_lat=19.070")
    assert res.status_code == 200
    data = res.json()
    
    assert data["type"] == "FeatureCollection"
    assert data["metadata"]["bbox_filter_applied"] is True
    # Filtered count should be non-zero and less than total segments
    assert data["metadata"]["count"] > 0

def test_raw_and_processed_files_separation():
    """Verify that raw files are stored separately from processed GeoJSON and GeoPackage files."""
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "openstreetmap"))
    processed_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed", "openstreetmap"))
    
    assert os.path.isdir(raw_dir), f"Raw OSM directory does not exist: {raw_dir}"
    assert os.path.isdir(processed_dir), f"Processed OSM directory does not exist: {processed_dir}"
    
    # Check that raw contains .osm XML files
    raw_files = [f for f in os.listdir(raw_dir) if f.endswith(".osm")]
    assert len(raw_files) >= 1, "At least one raw .osm file must be saved in raw directory"
    
    # Check that processed contains .geojson and .gpkg files
    processed_files = os.listdir(processed_dir)
    assert any(f.endswith(".geojson") for f in processed_files), "Processed directory must contain GeoJSON"
    assert any(f.endswith(".gpkg") for f in processed_files), "Processed directory must contain GeoPackage"

def test_ingestion_idempotence():
    """Verify that repeated upsert runs do not duplicate database records."""
    db = SessionLocal()
    try:
        initial_count = db.query(RoadSegment).count()
        assert initial_count > 0, "Database must already have road segments ingested"
        
        # Instantiate pipeline and re-run upsert with existing data
        pipeline = OSMRealDataIngestionPipeline()
        import geopandas as gpd
        processed_roads_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "processed", "openstreetmap", "mumbai_roads_real.geojson"
        )
        processed_fac_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "processed", "openstreetmap", "mumbai_facilities_real.geojson"
        )
        
        if os.path.exists(processed_roads_path) and os.path.exists(processed_fac_path):
            edges = gpd.read_file(processed_roads_path)
            fac = gpd.read_file(processed_fac_path)
            new_inserted = pipeline.upsert_database_records(edges, fac, db=db)
            assert new_inserted == 0, f"Expected 0 new inserts on re-run, got {new_inserted}"
            
            final_count = db.query(RoadSegment).count()
            assert final_count == initial_count, f"Record count changed from {initial_count} to {final_count}"
    finally:
        db.close()
