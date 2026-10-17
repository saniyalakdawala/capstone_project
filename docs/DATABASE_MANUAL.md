# EIDT Database Architecture & PostGIS Manual

## 1. Relational & Spatial Architecture

The Earth Intelligence Digital Twin (EIDT) stores structured environmental, meteorological, remote sensing, infrastructural, and simulation records in PostgreSQL with spatial extensions.

### Schema Entities (Section 8)

1. **`study_areas`**: Administrative ward polygons (e.g., Kurla Ward L, Sion Ward F/North, BKC Ward H/East), areas, population counts, and average elevation.
2. **`weather_observations`**: Time-series precipitation, temperature, humidity, wind speed from IMD Santacruz/Colaba AWS and NASA GPM.
3. **`satellite_observations`**: Metadata for Sentinel-1 C-SAR GRD and Sentinel-2 MSI scenes, acquisition footprints, sensor parameters, and polarization channels.
4. **`environmental_features`**: River channels (Mithi River, Oshiwara River), drainage canals, DEM grid cells, land-use classifications.
5. **`infrastructure`**: Critical facilities (trauma centers, municipal hospitals, schools, emergency shelters, fire stations) with point geometries and operational attributes (bed count, ICU units, emergency boats).
6. **`road_segments`**: Arterial transport network with topological connectivity attributes, speed limits, lengths, and flood vulnerability indices.
7. **`flood_events`**: Historical ground-truth benchmarks (July 2005 deluge, August 2017 floods, July 2019 event) with validated flood extent polygons.
8. **`model_runs`**: Version tracking for AI/ML models (Random Forest v1.4.2, SCS-CN Hydrological v1.1.0) and evaluation metadata (ROC-AUC, F1, IoU).
9. **`scenarios`**: User-configured simulation scenarios (rainfall accumulation mm, duration, soil saturation %, high tide height m, mitigation flags).
10. **`simulation_results`**: Computed spatial risk metrics, 95% confidence intervals, epistemic uncertainty, per-ward exposure breakdowns, and accessibility reductions.

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
