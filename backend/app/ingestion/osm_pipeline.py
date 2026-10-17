"""
Real-Data OpenStreetMap Ingestion Pipeline using Python & OSMnx (Section 20 Deliverable)
Retrieves real road networks, hospitals, schools, and waterways for Mumbai.
Validates CRS (EPSG:4326), checks geometries, stores raw OSM data separately from
processed GeoJSON / GeoPackage / PostgreSQL records, and provides idempotent upsert.
"""
import os
import sys
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely import make_valid

import osmnx as ox
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, engine
from app.models.schema import RoadSegment, Infrastructure, EnvironmentalFeature

RAW_OSM_DIR = os.path.join(settings.DATA_DIR, "..", "..", "data", "raw", "openstreetmap")
PROCESSED_OSM_DIR = os.path.join(settings.DATA_DIR, "..", "..", "data", "processed", "openstreetmap")
os.makedirs(RAW_OSM_DIR, exist_ok=True)
os.makedirs(PROCESSED_OSM_DIR, exist_ok=True)

# Mumbai Pilot Bounding Box: Kurla, BKC, Mithi River Corridor
DEFAULT_MUMBAI_BBOX = (72.855, 19.050, 72.890, 72.078)  # fallback
PILOT_KURLA_BBOX = (72.860, 19.055, 72.885, 19.075)     # (min_lon, min_lat, max_lon, max_lat)

class OSMRealDataIngestionPipeline:
    def __init__(self, bbox: Tuple[float, float, float, float] = PILOT_KURLA_BBOX):
        self.bbox = bbox
        self.min_lon, self.min_lat, self.max_lon, self.max_lat = bbox
        self.user_agent = "EarthIntelligenceDigitalTwin-Mumbai/1.0 (contact: eidt-mumbai@research.org)"
        self.provenance: Dict[str, Any] = {}

    def fetch_raw_osm(self) -> str:
        """
        Downloads real raw OSM XML directly from the official OpenStreetMap API
        following the OpenStreetMap usage policy.
        """
        url = (
            f"https://api.openstreetmap.org/api/0.6/map?"
            f"bbox={self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"
        )
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        raw_filename = f"mumbai_raw_{timestamp_str}.osm"
        raw_filepath = os.path.join(RAW_OSM_DIR, raw_filename)

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=45) as resp:
            content = resp.read()

        with open(raw_filepath, "wb") as f:
            f.write(content)

        print(f"[OSM Ingestion] Downloaded {len(content):,} bytes of raw OpenStreetMap XML to: {raw_filepath}")
        return raw_filepath

    def process_road_network_with_osmnx(self, raw_osm_path: str) -> gpd.GeoDataFrame:
        """
        Uses OSMnx to construct the topological road network graph from the raw OSM XML.
        Validates geometries and CRS to EPSG:4326.
        """
        print("[OSM Ingestion] Parsing road graph using OSMnx...")
        G = ox.graph_from_xml(raw_osm_path, bidirectional=True)
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)

        # Validate CRS
        if gdf_edges.crs is None:
            gdf_edges.set_crs(epsg=4326, inplace=True)
        elif gdf_edges.crs.to_epsg() != 4326:
            gdf_edges = gdf_edges.to_crs(epsg=4326)

        # Validate and fix geometries
        gdf_edges["geometry"] = gdf_edges["geometry"].apply(lambda geom: make_valid(geom) if geom and not geom.is_valid else geom)
        gdf_edges = gdf_edges[~gdf_edges["geometry"].is_empty & gdf_edges["geometry"].notna()]

        # Clean list columns so they can be serialized to JSON / GeoPackage cleanly
        for col in gdf_edges.columns:
            if col != "geometry":
                gdf_edges[col] = gdf_edges[col].apply(lambda x: ", ".join(map(str, x)) if isinstance(x, list) else x)

        print(f"[OSM Ingestion] Successfully extracted {len(gdf_edges)} valid real road segments using OSMnx.")
        return gdf_edges

    def process_amenities_and_waterways(self, raw_osm_path: str) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Parses hospitals, schools, and waterways from the downloaded OSM XML.
        """
        tree = ET.parse(raw_osm_path)
        root = tree.getroot()

        # Parse nodes map: id -> (lon, lat)
        nodes_dict = {}
        hospitals = []
        schools = []
        waterways = []

        for node in root.findall("node"):
            nid = node.get("id")
            lat = float(node.get("lat"))
            lon = float(node.get("lon"))
            nodes_dict[nid] = (lon, lat)

            # Check amenity tags
            tags = {tag.get("k"): tag.get("v") for tag in node.findall("tag")}
            amenity = tags.get("amenity")
            if amenity == "hospital":
                hospitals.append({
                    "id": f"OSM_NODE_{nid}",
                    "name": tags.get("name", "Hospital Facility"),
                    "type": "hospital",
                    "lat": lat, "lon": lon,
                    "operator": tags.get("operator", "Public / BMC"),
                    "geometry": Point(lon, lat)
                })
            elif amenity == "school":
                schools.append({
                    "id": f"OSM_NODE_{nid}",
                    "name": tags.get("name", "School Facility"),
                    "type": "school",
                    "lat": lat, "lon": lon,
                    "geometry": Point(lon, lat)
                })

        # Parse ways for waterways & hospital/school areas
        for way in root.findall("way"):
            wid = way.get("id")
            tags = {tag.get("k"): tag.get("v") for tag in way.findall("tag")}
            way_nodes = [nd.get("ref") for nd in way.findall("nd")]
            coords = [nodes_dict[nid] for nid in way_nodes if nid in nodes_dict]

            if len(coords) >= 2:
                # Waterway (Mithi River channels, canals)
                if "waterway" in tags or tags.get("natural") == "water":
                    waterways.append({
                        "id": f"OSM_WAY_{wid}",
                        "name": tags.get("name", tags.get("waterway", "Mithi River Canal")),
                        "type": "River",
                        "waterway_class": tags.get("waterway", "drain"),
                        "geometry": LineString(coords)
                    })

                # Hospital or School polygon
                amenity = tags.get("amenity")
                if amenity in ["hospital", "school"] and len(coords) >= 4:
                    poly = Polygon(coords)
                    poly = make_valid(poly)
                    centroid = poly.centroid
                    target_list = hospitals if amenity == "hospital" else schools
                    target_list.append({
                        "id": f"OSM_WAY_{wid}",
                        "name": tags.get("name", f"{amenity.capitalize()} Facility"),
                        "type": amenity,
                        "lat": centroid.y, "lon": centroid.x,
                        "geometry": centroid
                    })

        # Create GeoDataFrames
        facilities = hospitals + schools
        if facilities:
            gdf_facilities = gpd.GeoDataFrame(facilities, crs="EPSG:4326")
        else:
            gdf_facilities = gpd.GeoDataFrame(columns=["id", "name", "type", "lat", "lon", "geometry"], crs="EPSG:4326")

        if waterways:
            gdf_waterways = gpd.GeoDataFrame(waterways, crs="EPSG:4326")
        else:
            gdf_waterways = gpd.GeoDataFrame(columns=["id", "name", "type", "waterway_class", "geometry"], crs="EPSG:4326")

        print(f"[OSM Ingestion] Extracted {len(hospitals)} hospitals, {len(schools)} schools, and {len(waterways)} waterways.")
        return gdf_facilities, gdf_waterways

    def save_processed_formats(
        self,
        gdf_edges: gpd.GeoDataFrame,
        gdf_facilities: gpd.GeoDataFrame,
        gdf_waterways: gpd.GeoDataFrame
    ) -> Dict[str, str]:
        """
        Saves processed data into GeoJSON and GeoPackage fallback formats.
        """
        roads_geojson_path = os.path.join(PROCESSED_OSM_DIR, "mumbai_roads_real.geojson")
        facilities_geojson_path = os.path.join(PROCESSED_OSM_DIR, "mumbai_facilities_real.geojson")
        waterways_geojson_path = os.path.join(PROCESSED_OSM_DIR, "mumbai_waterways_real.geojson")
        gpkg_path = os.path.join(PROCESSED_OSM_DIR, "mumbai_osm.gpkg")

        # 1. GeoJSON exports (also copy to backend/app/data for immediate frontend consumption)
        gdf_edges.to_file(roads_geojson_path, driver="GeoJSON")
        # Also copy to frontend served static data location
        frontend_roads_path = os.path.join(settings.DATA_DIR, "mumbai_roads_real.geojson")
        gdf_edges.to_file(frontend_roads_path, driver="GeoJSON")

        gdf_facilities.to_file(facilities_geojson_path, driver="GeoJSON")
        gdf_waterways.to_file(waterways_geojson_path, driver="GeoJSON")

        # 2. GeoPackage fallback (multi-layer container)
        try:
            gdf_edges.to_file(gpkg_path, layer="roads", driver="GPKG")
            gdf_facilities.to_file(gpkg_path, layer="facilities", driver="GPKG")
            gdf_waterways.to_file(gpkg_path, layer="waterways", driver="GPKG")
            print(f"[OSM Ingestion] Successfully saved multi-layer GeoPackage to: {gpkg_path}")
        except Exception as e:
            print(f"[OSM Ingestion] Note on GPKG export: {e}")

        return {
            "roads_geojson": roads_geojson_path,
            "facilities_geojson": facilities_geojson_path,
            "waterways_geojson": waterways_geojson_path,
            "geopackage": gpkg_path
        }

    def upsert_database_records(
        self,
        gdf_edges: gpd.GeoDataFrame,
        gdf_facilities: gpd.GeoDataFrame,
        db: Optional[Session] = None
    ) -> int:
        """
        Idempotent database upsert into PostgreSQL/PostGIS road_segments and infrastructure tables.
        Prevents record duplication by checking primary keys with bulk set lookup.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        inserted_roads = 0
        inserted_infra = 0

        try:
            # 1. Bulk lookup of existing IDs to avoid slow per-row round-trips
            existing_road_ids = set(r[0] for r in db.query(RoadSegment.road_segment_id).all())
            existing_infra_ids = set(r[0] for r in db.query(Infrastructure.infrastructure_id).all())

            # 2. Batch process Roads
            batch = []
            for idx, row in gdf_edges.iterrows():
                u_val = row.get("u")
                v_val = row.get("v")
                key_val = row.get("key", 0)
                if pd.notna(u_val) and pd.notna(v_val):
                    road_id = f"OSM_{u_val}_{v_val}_{key_val}"[:64]
                else:
                    osmid = row.get("osmid")
                    osmid_str = "_".join(map(str, osmid)) if isinstance(osmid, list) else str(osmid)
                    road_id = f"OSM_{osmid_str}_{idx}"[:64]
                
                if road_id in existing_road_ids:
                    continue

                existing_road_ids.add(road_id)
                highway_class = str(row.get("highway", "residential"))[:64]
                name_val = str(row.get("name", "Unnamed Road"))[:255] if pd.notna(row.get("name")) else "Unnamed Road"
                
                raw_len = row.get("length", 100.0)
                length_val = 100.0
                if pd.notna(raw_len):
                    try:
                        length_val = round(min(max(float(raw_len), 0.1), 9999999.99), 2)
                    except (ValueError, TypeError):
                        length_val = 100.0
                
                speed_raw = row.get("maxspeed")
                speed_val = 40.0
                if pd.notna(speed_raw):
                    first_token = str(speed_raw).replace(";", " ").replace(",", " ").split()[0]
                    digits = "".join(c for c in first_token if c.isdigit() or c == ".")
                    if digits:
                        try:
                            parsed_s = float(digits)
                            if 5.0 <= parsed_s <= 140.0:
                                speed_val = round(parsed_s, 1)
                        except (ValueError, TypeError):
                            speed_val = 40.0

                vuln = 0.85 if ("tertiary" in highway_class or "residential" in highway_class) else 0.40
                vuln = round(min(max(vuln, 0.0), 1.0), 2)
                geom_json = mapping(row["geometry"])

                lanes_val = str(row.get("lanes", "2")) if pd.notna(row.get("lanes")) else "2"
                oneway_val = str(row.get("oneway", "False")) if pd.notna(row.get("oneway")) else "False"

                new_road = RoadSegment(
                    road_segment_id=road_id,
                    name=name_val,
                    road_class=highway_class,
                    geometry=geom_json,
                    length_meters=length_val,
                    speed_kmh=speed_val,
                    connectivity_attributes={"lanes": lanes_val, "oneway": oneway_val},
                    vulnerability_index=vuln,
                    source="OpenStreetMap (Live OSMnx Ingestion)"
                )
                batch.append(new_road)
                inserted_roads += 1

                if len(batch) >= 500:
                    db.bulk_save_objects(batch)
                    db.commit()
                    batch = []

            if batch:
                db.bulk_save_objects(batch)
                db.commit()

            # 3. Batch process Facilities
            infra_batch = []
            for idx, row in gdf_facilities.iterrows():
                infra_id = str(row["id"])[:64]
                if infra_id in existing_infra_ids:
                    continue

                existing_infra_ids.add(infra_id)
                geom_json = mapping(row["geometry"])
                op_val = str(row.get("operator")) if pd.notna(row.get("operator")) else "Public / Municipal"
                name_val = str(row.get("name", "Facility"))[:255]

                new_inf = Infrastructure(
                    infrastructure_id=infra_id,
                    feature_type=str(row["type"])[:64],
                    name=name_val,
                    geometry=geom_json,
                    latitude=float(row["lat"]),
                    longitude=float(row["lon"]),
                    ward_id="MUM_WARD_L_KURLA",
                    properties={"operator": op_val},
                    source="OpenStreetMap Contributors (ODbL 1.0)"
                )
                infra_batch.append(new_inf)
                inserted_infra += 1

            if infra_batch:
                db.bulk_save_objects(infra_batch)
                db.commit()

            print(f"[OSM Ingestion] Database upsert completed: {inserted_roads} new road segments, {inserted_infra} new facilities.")
        except Exception as e:
            db.rollback()
            print(f"[OSM Ingestion] Error during database upsert: {e}")
            raise e
        finally:
            if close_db:
                db.close()

        return inserted_roads

    def run(self) -> Dict[str, Any]:
        """
        Executes end-to-end OSM real data pipeline and records provenance.
        """
        start_time = datetime.now(timezone.utc)
        print(f"[OSM Ingestion] Starting real OpenStreetMap ingestion for bbox: {self.bbox}")

        raw_path = self.fetch_raw_osm()
        gdf_edges = self.process_road_network_with_osmnx(raw_path)
        gdf_facilities, gdf_waterways = self.process_amenities_and_waterways(raw_path)
        saved_paths = self.save_processed_formats(gdf_edges, gdf_facilities, gdf_waterways)
        self.upsert_database_records(gdf_edges, gdf_facilities)

        end_time = datetime.now(timezone.utc)
        duration_s = (end_time - start_time).total_seconds()

        self.provenance = {
            "source_name": "OpenStreetMap",
            "access_mechanism": "OSMnx 2.1 & Official OSM API 0.6",
            "study_area_bbox": list(self.bbox),
            "study_area_name": "Mumbai Pilot (Kurla / BKC Corridor)",
            "retrieval_timestamp": end_time.isoformat(),
            "duration_seconds": round(duration_s, 2),
            "features_retrieved": {
                "road_segments_count": len(gdf_edges),
                "nodes_count": len(gdf_edges) + len(gdf_facilities),
                "facilities_count": len(gdf_facilities),
                "waterways_count": len(gdf_waterways)
            },
            "status": "SUCCESS_REAL_DATA",
            "crs": "EPSG:4326 (WGS84)",
            "attribution": "Map data © OpenStreetMap contributors, ODbL 1.0",
            "raw_storage_path": raw_path,
            "processed_storage": saved_paths
        }

        # Save provenance record
        prov_file = os.path.join(PROCESSED_OSM_DIR, "osm_real_data_provenance.json")
        with open(prov_file, "w", encoding="utf-8") as f:
            json.dump(self.provenance, f, indent=2)

        return self.provenance

# Helper mapping import for geometries
from shapely.geometry import mapping

if __name__ == "__main__":
    pipeline = OSMRealDataIngestionPipeline()
    result = pipeline.run()
    print("Execution Result Summary:")
    print(json.dumps(result, indent=2))
