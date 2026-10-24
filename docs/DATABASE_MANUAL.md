# EIDT Database Architecture & PostGIS Manual

## 1. Relational & Spatial Architecture

The Earth Intelligence Digital Twin (EIDT) stores structured environmental, meteorological, remote sensing, infrastructural, and simulation records in PostgreSQL with spatial extensions.

### Schema Entities (Section 8 & MMR Phase 1 Upgrade)

1. **`study_areas`**: Administrative polygons with regional hierarchy (`parent_region_id`, `region_type`, `hierarchy_path`), areas, population counts, and average elevation.
2. **`weather_observations`**: Time-series precipitation, temperature, humidity, wind speed from IMD Santacruz/Colaba AWS and NASA GPM.
3. **`satellite_observations`**: Metadata for Sentinel-1 C-SAR GRD and Sentinel-2 MSI scenes, acquisition footprints, sensor parameters, and polarization channels.
4. **`environmental_features`**: River channels (Mithi River, Oshiwara River), drainage canals, DEM grid cells, land-use classifications.
5. **`infrastructure`**: Critical facilities with locality metadata (`locality_name`, `sub_ward`), point geometries, and operational attributes.
6. **`road_segments`**: Arterial transport network with locality identifiers (`locality_name`, `elevation_m`), speed limits, lengths, and flood vulnerability indices.
7. **`flood_events`**: Historical ground-truth benchmarks (July 2005 deluge, August 2017 floods, July 2019 event) with validated flood extent polygons.
8. **`model_runs`**: Version tracking for AI/ML models (Random Forest v1.4.2, SCS-CN Hydrological v1.1.0) and evaluation metadata (ROC-AUC, F1, IoU).
9. **`scenarios`**: User-configured simulation scenarios (rainfall accumulation mm, duration, soil saturation %, high tide height m, mitigation flags).
10. **`simulation_results`**: Computed spatial risk metrics, 95% confidence intervals, epistemic uncertainty, per-ward exposure breakdowns, and accessibility reductions.
11. **`buildings`**: High-resolution building footprints, structural typology, height/levels, ground elevation, and structural flood susceptibility.
12. **`locality_alerts`**: Actionable flood early warning advisories keyed to specific urban localities with severity levels and recommended civil actions.
13. **`data_provenance_logs`**: Automated acquisition audit trail recording ingestion timestamps, source connectors, checksums, and record counts.
14. **`schema_migrations`**: Idempotent migration ledger tracking applied schema versions.
15. **`emergency_facilities`**: Verified hospitals, trauma centres, fire stations, police stations, and officially designated evacuation shelters with verified capacities.
16. **`road_restrictions`**: Active verified road closures, underpass flood blockages, speed reductions, and scenario closures.
17. **`route_requests`**: Logged routing requests and computed metrics (distance km, travel duration, waterlogged segment count, uncertainty notices).
18. **`evacuation_scenarios`**: User-defined hypothetical road closure scenarios for emergency exercise simulation.


---

## 2. Spatial Indexing & Why PostGIS is Essential

### Advantages of PostGIS for EIDT:
- **Spatial Indexing (`GIST` / R-Tree):** Enables fast bounding box pruning for spatial joins. Rather than performing $O(N \times M)$ pairwise geometric comparisons between 10,000 infrastructure points and flood polygons, the R-tree index reduces search complexity to $O(\log N)$.
- **Native Spatial Topology & Distance Operators:** PostGIS provides geodesic distance (`ST_Distance`), buffer generation (`ST_Buffer`), geometric intersection (`ST_Intersects`), and area calculation (`ST_Area`), preserving metric accuracy across EPSG:32643 (UTM Zone 43N).
- **Dual Support Fallback:** EIDT's SQLAlchemy models support native PostGIS geometry types while also maintaining GeoJSON/WKT column serialization for local portable deployments.

---

## 3. Benchmark GIS-Aware SQL Queries (Section 14)

### Query 1: Critical Hospitals within Predicted Inundation Zones
```sql
EXPLAIN ANALYZE
SELECT 
    h.infrastructure_id, 
    h.name AS hospital_name, 
    h.properties->>'beds' AS bed_capacity,
    w.name AS ward_name,
    s.scenario_name,
    (sr.summary_metrics->>'high_risk_area_sqkm')::numeric AS flooded_sqkm
FROM infrastructure h
JOIN study_areas w ON h.ward_id = w.study_area_id
JOIN scenarios s ON s.study_area_id = w.study_area_id
JOIN simulation_results sr ON sr.scenario_id = s.scenario_id
WHERE h.feature_type = 'hospital'
  AND s.scenario_id = 'SCEN_HEAVY_200MM';
```

### Query 2: Aggregate Demographic Exposure by Ward
```sql
SELECT 
    sa.name AS ward_name,
    sa.population AS total_ward_population,
    COALESCE((sr.ward_breakdown->sa.study_area_id->>'exposed_pop')::numeric, 0) AS estimated_exposed_residents,
    ROUND(
        ((sr.ward_breakdown->sa.study_area_id->>'exposed_pop')::numeric / sa.population * 100), 
        2
    ) AS exposure_percentage,
    sr.ward_breakdown->sa.study_area_id->>'risk_category' AS risk_classification
FROM study_areas sa
JOIN simulation_results sr ON sr.result_type = 'flood_risk_synthesis'
WHERE sr.scenario_id = 'SCEN_EXTREME_300MM'
ORDER BY exposure_percentage DESC;
```

### Query 3: Retrieve Submerged Corridors and Severed Hospital Links
```sql
SELECT 
    r.road_segment_id,
    r.name AS corridor_name,
    r.road_class,
    r.vulnerability_index,
    r.speed_kmh AS normal_speed_kmh,
    CASE 
        WHEN r.vulnerability_index >= 0.80 THEN 'IMPASSABLE / SUBMERGED'
        WHEN r.vulnerability_index >= 0.50 THEN 'SEVERE WATERLOGGING (8 KM/H)'
        ELSE 'PASSABLE'
    END AS simulated_status
FROM road_segments r
ORDER BY r.vulnerability_index DESC;
```

### Query 4: Designated Evacuation Shelters with Verified Capacity Balance
```sql
SELECT 
    f.facility_id,
    f.name AS shelter_name,
    f.locality_name,
    f.ward_id,
    f.capacity_total AS verified_capacity,
    f.capacity_available AS current_available_capacity,
    f.operating_status,
    f.source_name AS verification_source,
    f.last_verified_at
FROM emergency_facilities f
WHERE f.is_officially_designated_shelter = TRUE
  AND f.operating_status = 'OPERATIONAL'
ORDER BY f.capacity_total DESC NULLS LAST;
```

