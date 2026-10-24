import sqlite3
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.services.geo_hierarchy import (
    MAHARASHTRA_STATE, MAHARASHTRA_DIVISIONS, MAHARASHTRA_DISTRICTS,
    PILOT_WARD_DISTRICT_MAP, bbox_to_polygon_geojson, MAHARASHTRA_PROVENANCE
)

db_path = os.path.join(os.path.dirname(__file__), "..", "backend", "eidt_mumbai.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

all_items = [MAHARASHTRA_STATE] + MAHARASHTRA_DIVISIONS + MAHARASHTRA_DISTRICTS

for d in all_items:
    sid = d["study_area_id"]
    name = d["name"]
    adm_level = d.get("administrative_level", "District")
    reg_type = d.get("region_type", "District")
    pid = d.get("parent_region_id", d.get("division_id"))
    div_id = d.get("division_id")
    dist_id = d.get("study_area_id") if reg_type == "District" else None
    hpath = d.get("hierarchy_path", f"MAH_STATE/{div_id}/{sid}")
    aliases = json.dumps(d.get("aliases", []))
    bbox = json.dumps(d.get("bounding_box", []))
    geom = json.dumps(bbox_to_polygon_geojson(d["bounding_box"]))
    area = d.get("area_sq_km")
    pop = d.get("population")
    elev = d.get("elevation_mean_m")

    cur.execute("""
        INSERT OR REPLACE INTO study_areas (
            study_area_id, name, administrative_level, region_type, parent_region_id,
            division_id, district_id, hierarchy_path, aliases, bounding_box, geometry,
            area_sq_km, population, elevation_mean_m, source, boundary_version, crs, is_verified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        sid, name, adm_level, reg_type, pid, div_id, dist_id, hpath,
        aliases, bbox, geom, area, pop, elev,
        MAHARASHTRA_PROVENANCE["source"], MAHARASHTRA_PROVENANCE["boundary_version"], "EPSG:4326"
    ))

# Update pilot wards
for ward_id, parent_dist_id in PILOT_WARD_DISTRICT_MAP.items():
    cur.execute("""
        UPDATE study_areas 
        SET parent_region_id = ?, district_id = ?, division_id = 'DIV_KONKAN',
            hierarchy_path = ?, boundary_version = 'BMC-GIS-2021-v1.0', crs = 'EPSG:4326', is_verified = 1
        WHERE study_area_id = ?
    """, (parent_dist_id, parent_dist_id, f"MAH_STATE/DIV_KONKAN/{parent_dist_id}/{ward_id}", ward_id))

conn.commit()
count = cur.execute("SELECT COUNT(*) FROM study_areas;").fetchone()[0]
print(f"SQLite database synchronized: {count} study areas present.")
conn.close()
