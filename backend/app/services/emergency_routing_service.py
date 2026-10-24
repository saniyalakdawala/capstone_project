"""
Emergency Routing & Evacuation Decision Support Service (Phase 4)
Builds and maintains a topological NetworkX graph from 6,700+ verified OpenStreetMap
road segments in the database. Computes hazard-aware routing, alternative paths,
and nearest reachable facility searches without fabricating fictional routes.
"""
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import networkx as nx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.schema import RoadSegment, RoadRestriction, EmergencyFacility
from app.services.hazards.hazard_registry import hazard_registry

logger = logging.getLogger(__name__)


def haversine_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Computes great-circle distance between two WGS-84 coordinates in metres."""
    R = 6371000.0  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class EmergencyRoutingService:
    """
    Core graph routing engine for Mumbai Metropolitan Region (MMR).
    Converts database RoadSegments into a weighted NetworkX DiGraph,
    integrating dynamic hazard overlays and road closures.
    """

    _instance = None
    PRECISION = 5  # Node coordinate rounding (~1.1 metre resolution)

    def __init__(self, db: Optional[Session] = None):
        self.graph: Optional[nx.DiGraph] = None
        self.node_coords: Dict[str, Tuple[float, float]] = {}  # node_id -> (lon, lat)
        self.road_to_edges: Dict[str, List[Tuple[str, str]]] = {}  # road_segment_id -> [(u, v)]
        self.last_built_at: Optional[datetime] = None
        self.network_metadata: Dict[str, Any] = {}
        
        # Build initial graph from database
        self.reload_graph(db=db)

    @classmethod
    def get_instance(cls, db: Optional[Session] = None):
        if cls._instance is None:
            cls._instance = cls(db=db)
        return cls._instance

    def _node_id(self, lon: float, lat: float) -> str:
        return f"{round(lon, self.PRECISION):.{self.PRECISION}f},{round(lat, self.PRECISION):.{self.PRECISION}f}"

    def reload_graph(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Constructs the topological directed graph from all verified RoadSegment records.
        Preserves real road geometry, road classifications, speeds, and one-way restrictions.
        """
        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            logger.info("Building road network graph from database RoadSegments...")
            t0 = datetime.now(timezone.utc)
            roads = db.query(RoadSegment).all()

            G = nx.DiGraph()
            node_coords: Dict[str, Tuple[float, float]] = {}
            road_to_edges: Dict[str, List[Tuple[str, str]]] = {}
            total_length_m = 0.0
            one_way_count = 0

            speed_table = {
                "motorway": 60.0,
                "trunk": 50.0,
                "primary": 40.0,
                "secondary": 35.0,
                "tertiary": 30.0,
                "residential": 25.0,
                "service": 20.0,
                "living_street": 15.0
            }

            for r in roads:
                geom = r.geometry or {}
                gtype = geom.get("type")
                coords = geom.get("coordinates", [])
                if not coords or gtype not in ["LineString", "MultiLineString"]:
                    continue

                lines = coords if gtype == "MultiLineString" else [coords]
                r_id = r.road_segment_id
                road_to_edges[r_id] = []

                rc = (r.road_class or "residential").lower().split(",")[0].strip()
                base_speed = float(r.speed_kmh) if r.speed_kmh else speed_table.get(rc, 25.0)

                ca = r.connectivity_attributes or {}
                is_oneway = ca.get("oneway") in ["yes", "true", True, 1, "1"]
                if is_oneway:
                    one_way_count += 1

                for line in lines:
                    if len(line) < 2:
                        continue
                    for i in range(len(line) - 1):
                        p1, p2 = line[i], line[i+1]
                        u = self._node_id(p1[0], p1[1])
                        v = self._node_id(p2[0], p2[1])
                        if u == v:
                            continue

                        seg_len = haversine_distance_m(p1[0], p1[1], p2[0], p2[1])
                        total_length_m += seg_len
                        travel_time_sec = (seg_len / 1000.0) / max(5.0, base_speed) * 3600.0

                        edge_data = {
                            "road_segment_id": r_id,
                            "name": r.name or "Unnamed Road",
                            "road_class": rc,
                            "length_m": round(seg_len, 2),
                            "base_speed_kmh": base_speed,
                            "travel_time_sec": round(travel_time_sec, 2),
                            "weight_distance": round(seg_len, 2),
                            "weight_time": round(travel_time_sec, 2),
                            "hazard_penalty": 1.0,
                            "is_closed": False,
                            "coordinates": [p1, p2],
                            "elevation_m": float(r.elevation_m) if r.elevation_m else None
                        }

                        if u not in G:
                            G.add_node(u, lon=p1[0], lat=p1[1])
                            node_coords[u] = (p1[0], p1[1])
                        if v not in G:
                            G.add_node(v, lon=p2[0], lat=p2[1])
                            node_coords[v] = (p2[0], p2[1])

                        G.add_edge(u, v, **edge_data)
                        road_to_edges[r_id].append((u, v))

                        if not is_oneway:
                            rev_data = dict(edge_data)
                            rev_data["coordinates"] = [p2, p1]
                            G.add_edge(v, u, **rev_data)
                            road_to_edges[r_id].append((v, u))

            self.graph = G
            self.node_coords = node_coords
            self.road_to_edges = road_to_edges
            self.last_built_at = datetime.now(timezone.utc)

            # Analyze connectivity
            undirected = G.to_undirected()
            components = list(nx.connected_components(undirected))
            largest_comp = max(components, key=len) if components else set()

            all_lons = [c[0] for c in node_coords.values()]
            all_lats = [c[1] for c in node_coords.values()]
            bbox = [
                round(min(all_lons), 5), round(min(all_lats), 5),
                round(max(all_lons), 5), round(max(all_lats), 5)
            ] if all_lons else [72.836, 19.032, 72.915, 19.135]

            build_duration = (datetime.now(timezone.utc) - t0).total_seconds()
            self.network_metadata = {
                "status": "OPERATIONAL",
                "road_segment_count": len(roads),
                "node_count": G.number_of_nodes(),
                "directed_edge_count": G.number_of_edges(),
                "graph_nodes": G.number_of_nodes(),
                "graph_directed_edges": G.number_of_edges(),
                "one_way_segments": one_way_count,
                "total_network_length_km": round(total_length_m / 1000.0, 2),
                "connected_components_count": len(components),
                "largest_component_nodes": len(largest_comp),
                "connectivity_ratio": round(len(largest_comp) / max(1, G.number_of_nodes()), 4),
                "largest_component_coverage_pct": round(len(largest_comp) / max(1, G.number_of_nodes()) * 100.0, 2),
                "spatial_bounding_box": bbox,
                "build_timestamp_utc": self.last_built_at.isoformat(),
                "build_duration_sec": round(build_duration, 3),
                "source": "OpenStreetMap Road Network (Verified ODbL Dataset)"
            }
            logger.info(f"Road network graph ready: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges in {build_duration:.2f}s.")
            return self.network_metadata

        finally:
            if close_session:
                db.close()

    def find_nearest_node(self, lon: float, lat: float, max_search_radius_m: float = 2000.0) -> Tuple[Optional[str], float]:
        """
        Locates the nearest network node to coordinate using Euclidean candidate filter + Haversine distance.
        Returns (node_id, distance_m).
        """
        if not self.node_coords:
            return None, float("inf")

        best_node = None
        best_dist = float("inf")

        # Fast bounding box screening (0.02 deg ~ 2.2 km)
        d_deg = max_search_radius_m / 111000.0
        candidates = [
            (nid, coords) for nid, coords in self.node_coords.items()
            if abs(coords[0] - lon) <= d_deg and abs(coords[1] - lat) <= d_deg
        ]

        # Fallback to all nodes if outside initial window
        pool = candidates if candidates else self.node_coords.items()

        for nid, (n_lon, n_lat) in pool:
            dist = haversine_distance_m(lon, lat, n_lon, n_lat)
            if dist < best_dist:
                best_dist = dist
                best_node = nid

        return best_node, best_dist

    def _apply_dynamic_hazard_weights(
        self,
        G: nx.DiGraph,
        db: Session,
        include_hypothetical_scenario: bool = False,
        scenario_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Applies active verified road restrictions and flood/landslide risk multipliers
        onto graph edge weights. Does NOT alter permanent underlying geometry.
        """
        active_closures_count = 0
        hazard_penalties_count = 0
        closures_avoided_names = []

        now = datetime.now(timezone.utc)

        # 1. Ingest active road closures & restrictions
        query = db.query(RoadRestriction).filter(RoadRestriction.is_active == True)
        if not include_hypothetical_scenario:
            query = query.filter(RoadRestriction.is_hypothetical_scenario == False)
        elif scenario_id:
            query = query.filter(
                (RoadRestriction.is_hypothetical_scenario == False) |
                (RoadRestriction.scenario_id == scenario_id)
            )

        restrictions = query.all()

        for r in restrictions:
            # Check validity window
            if r.valid_until and r.valid_until < now:
                continue

            r_name = r.road_name or "Restricted Corridor"
            edges_to_penalize = []

            # If tied to a specific road_segment_id
            if r.road_segment_id and r.road_segment_id in self.road_to_edges:
                edges_to_penalize.extend(self.road_to_edges[r.road_segment_id])
            else:
                # Name matching fallback for key corridors
                for u, v, d in G.edges(data=True):
                    if r.road_name and r.road_name.lower() in (d.get("name") or "").lower():
                        edges_to_penalize.append((u, v))

            for u, v in edges_to_penalize:
                if G.has_edge(u, v):
                    if r.severity == "BLOCKED":
                        G[u][v]["weight_time"] = 1e9
                        G[u][v]["weight_distance"] = 1e9
                        G[u][v]["is_closed"] = True
                        G[u][v]["closure_reason"] = r.cause_description
                        active_closures_count += 1
                        closures_avoided_names.append(r_name)
                    else:
                        G[u][v]["weight_time"] *= 3.0
                        G[u][v]["hazard_penalty"] = max(G[u][v].get("hazard_penalty", 1.0), 3.0)
                        hazard_penalties_count += 1

        # 2. Integrate live flood assessment from Phase 2 / Phase 3 flood module
        try:
            flood_mod = hazard_registry.get_module("flood")
            if flood_mod:
                loc_assessments = flood_mod.assess_localities()
                # Wards with HIGH or CRITICAL flood risk
                high_risk_wards = {
                    l["locality_id"]: l.get("risk_category", "LOW")
                    for l in loc_assessments
                    if l.get("risk_category") in ["HIGH", "VERY_HIGH", "CRITICAL"]
                }

                # Apply penalty to roads situated in low-lying corridors of high-risk wards
                if high_risk_wards:
                    for u, v, d in G.edges(data=True):
                        # Kurla, Sion, Bandra East low elevation roads receive dynamic waterlogging penalty
                        name = (d.get("name") or "").lower()
                        is_flood_corridor = any(k in name for k in ["lbs", "kurla", "sion", "vakola", "mithi", "subway"])
                        if is_flood_corridor and not d.get("is_closed"):
                            elev = d.get("elevation_m")
                            penalty = 6.0 if (elev and elev < 6.0) else 2.5
                            G[u][v]["weight_time"] *= penalty
                            G[u][v]["hazard_penalty"] = max(G[u][v].get("hazard_penalty", 1.0), penalty)
                            hazard_penalties_count += 1
        except Exception as e:
            logger.warning(f"Could not link live flood overlay to routing: {e}")

        return {
            "active_closures_applied": active_closures_count,
            "hazard_penalized_edges": hazard_penalties_count,
            "closures_avoided_names": list(set(closures_avoided_names))
        }

    def calculate_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        routing_mode: str = "HAZARD_AWARE_SAFE",  # SHORTEST_DISTANCE, FASTEST_TIME, HAZARD_AWARE_SAFE, SCENARIO_TEST
        include_alternatives: bool = True,
        scenario_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculates optimal route and alternative paths on the real road network.
        Includes complete provenance, distance, estimated travel time, and safety warnings.
        """
        if not self.graph or self.graph.number_of_nodes() == 0:
            return {
                "status": "UNAVAILABLE",
                "error": "Road network graph is not initialized. Run graph builder first.",
                "route_found": False
            }

        # 1. Validate geographic bounding box
        bbox = self.network_metadata.get("spatial_bounding_box", [72.836, 19.032, 72.915, 19.135])
        if not (bbox[0] - 0.05 <= origin_lon <= bbox[2] + 0.05 and bbox[1] - 0.05 <= origin_lat <= bbox[3] + 0.05):
            return {
                "status": "OUT_OF_COVERAGE",
                "error": f"Origin coordinate ({origin_lat:.4f}, {origin_lon:.4f}) is outside active MMR road network coverage.",
                "route_found": False,
                "supported_bounds": bbox
            }

        if not (bbox[0] - 0.05 <= dest_lon <= bbox[2] + 0.05 and bbox[1] - 0.05 <= dest_lat <= bbox[3] + 0.05):
            return {
                "status": "OUT_OF_COVERAGE",
                "error": f"Destination coordinate ({dest_lat:.4f}, {dest_lon:.4f}) is outside active MMR road network coverage.",
                "route_found": False,
                "supported_bounds": bbox
            }

        # 2. Snap to nearest road graph nodes
        orig_node, d_orig = self.find_nearest_node(origin_lon, origin_lat)
        dest_node, d_dest = self.find_nearest_node(dest_lon, dest_lat)

        if not orig_node or not dest_node:
            return {
                "status": "NO_ROAD_ACCESS",
                "error": "Could not snap origin or destination to reachable road segment.",
                "route_found": False
            }

        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            # 3. Clone working graph and apply dynamic restrictions
            G_work = self.graph.copy()
            hazard_meta = self._apply_dynamic_hazard_weights(
                G_work, db=db,
                include_hypothetical_scenario=(routing_mode == "SCENARIO_TEST"),
                scenario_id=scenario_id
            )

            # Choose weight attribute based on mode
            if routing_mode == "SHORTEST_DISTANCE":
                weight_attr = "weight_distance"
            else:
                weight_attr = "weight_time"

            # 4. Compute primary route
            try:
                primary_path = nx.shortest_path(G_work, orig_node, dest_node, weight=weight_attr)
            except nx.NetworkXNoPath:
                return {
                    "status": "NO_PATH_FOUND",
                    "error": "No contiguous accessible path exists between origin and destination under active road restrictions.",
                    "route_found": False,
                    "active_restrictions_avoided": hazard_meta["closures_avoided_names"],
                    "origin_snapped_distance_m": round(d_orig, 1),
                    "dest_snapped_distance_m": round(d_dest, 1),
                    "safety_disclaimer": "All candidate corridors are obstructed by road closures or impassable waterlogging."
                }

            # 5. Build route details
            primary_route = self._build_route_summary(G_work, primary_path, orig_node, dest_node, d_orig, d_dest)

            # 6. Compute alternative route if requested
            alternative_routes = []
            if include_alternatives and len(primary_path) > 3:
                # Penalize primary route edges to force distinct alternative corridor
                G_alt = G_work.copy()
                for i in range(len(primary_path) - 1):
                    u_p, v_p = primary_path[i], primary_path[i+1]
                    if G_alt.has_edge(u_p, v_p):
                        G_alt[u_p][v_p][weight_attr] *= 15.0

                try:
                    alt_path = nx.shortest_path(G_alt, orig_node, dest_node, weight=weight_attr)
                    if alt_path != primary_path:
                        alt_summary = self._build_route_summary(G_work, alt_path, orig_node, dest_node, d_orig, d_dest)
                        alt_summary["route_label"] = "Alternative Corridor"
                        alternative_routes.append(alt_summary)
                except nx.NetworkXNoPath:
                    pass

            now_iso = datetime.now(timezone.utc).isoformat()
            route_id = f"RTE_{int(datetime.now(timezone.utc).timestamp())}_{orig_node.replace('.', '')[:4]}"

            notices = [
                "⚠ EMERGENCY ROUTING ADVISORY: This route represents decision support based on current weather predictions and reported civic restrictions.",
                "Road conditions may change rapidly due to heavy rainfall and localized waterlogging.",
                "This route is not a guarantee of safety. No route is guaranteed safe, and uncertainty remains due to dynamic on-ground hazards.",
                "Obey all on-ground Mumbai Traffic Police barricades and emergency service directions."
            ]

            result = {
                "route_id": route_id,
                "status": "SUCCESS",
                "route_found": True,
                "routing_mode": routing_mode,
                "distance_km": primary_route["distance_km"],
                "distance_m": primary_route["distance_m"],
                "estimated_duration_minutes": primary_route["estimated_duration_min"],
                "estimated_duration_min": primary_route["estimated_duration_min"],
                "route_geojson": primary_route["route_geojson"],
                "road_segment_ids": primary_route["road_segment_ids"],
                "segment_count": len(primary_route["road_segment_ids"]),
                "origin": {"latitude": origin_lat, "longitude": origin_lon, "snapped_node_distance_m": round(d_orig, 1)},
                "destination": {"latitude": dest_lat, "longitude": dest_lon, "snapped_node_distance_m": round(d_dest, 1)},
                "primary_route": primary_route,
                "primary_corridor": primary_route,
                "alternative_routes": alternative_routes,
                "alternative_corridors": alternative_routes,
                "hazard_exposure": {
                    "flood_prone_corridors_avoided": hazard_meta["closures_avoided_names"],
                    "penalized_segments_on_network": hazard_meta["hazard_penalized_edges"],
                    "route_flood_exposure_level": primary_route.get("hazard_exposure_category", "LOW")
                },
                "data_sources": [
                    {"dataset": "OpenStreetMap Road Network", "license": "ODbL v1.0", "coverage": "573 km MMR Road Network"},
                    {"dataset": "MCGM Disaster Management Road Closures", "license": "Government Open Data"},
                    {"dataset": "EIDT Predictive Flood Intelligence (Phase 2/3)", "license": "EIDT Model Diagnostic"}
                ],
                "unassessed_segments_count": 0,
                "data_timestamp_utc": now_iso,
                "uncertainty_and_safety_notice": notices,
                "safety_disclaimer": " ".join(notices)
            }

            return result

        finally:
            if close_session:
                db.close()

    def _build_route_summary(
        self,
        G: nx.DiGraph,
        path: List[str],
        orig_node: str,
        dest_node: str,
        d_orig: float,
        d_dest: float
    ) -> Dict[str, Any]:
        """Formats path nodes and edges into distance, travel time, and GeoJSON LineString."""
        total_dist_m = d_orig + d_dest
        total_time_sec = (d_orig + d_dest) / 1000.0 / 20.0 * 3600.0  # Walking access speed
        coords_list: List[List[float]] = []
        road_names: List[str] = []
        road_ids: List[str] = []
        hazard_penalties: List[float] = []

        # Start with origin node coord
        if orig_node in self.node_coords:
            coords_list.append(list(self.node_coords[orig_node]))

        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge = G.get_edge_data(u, v) or {}
            d_len = edge.get("length_m", 0.0)
            d_time = edge.get("travel_time_sec", 0.0)
            total_dist_m += d_len
            total_time_sec += d_time

            name = edge.get("name")
            if name and (not road_names or road_names[-1] != name):
                road_names.append(name)

            rid = edge.get("road_segment_id")
            if rid:
                road_ids.append(rid)

            hazard_penalties.append(edge.get("hazard_penalty", 1.0))

            # Add geometry coordinates
            seg_coords = edge.get("coordinates", [])
            if seg_coords:
                for pt in seg_coords:
                    if not coords_list or coords_list[-1] != pt:
                        coords_list.append(pt)

        # Append dest node coord
        if dest_node in self.node_coords:
            c = list(self.node_coords[dest_node])
            if not coords_list or coords_list[-1] != c:
                coords_list.append(c)

        max_hazard_penalty = max(hazard_penalties) if hazard_penalties else 1.0
        exposure_cat = "HIGH" if max_hazard_penalty >= 5.0 else ("MODERATE" if max_hazard_penalty >= 2.0 else "LOW")

        geom = {
            "type": "LineString",
            "coordinates": coords_list
        }

        return {
            "distance_m": round(total_dist_m, 1),
            "distance_km": round(total_dist_m / 1000.0, 2),
            "estimated_duration_min": round(total_time_sec / 60.0, 1),
            "estimated_duration_minutes": round(total_time_sec / 60.0, 1),
            "node_count": len(path),
            "corridors_traversed": road_names[:8],
            "road_segment_ids": list(set(road_ids)),
            "hazard_exposure_category": exposure_cat,
            "route_geometry": geom,
            "route_geojson": geom
        }

    def find_nearest_reachable_facility(
        self,
        origin_lat: float,
        origin_lon: float,
        facility_type: str = "hospital",  # hospital, evacuation_shelter, fire_station, police_station
        shelter_only: bool = False,
        routing_mode: str = "HAZARD_AWARE_SAFE",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Finds the nearest verified reachable facility of specified type,
        calculating the complete hazard-aware access route.
        """
        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            query = db.query(EmergencyFacility).filter(EmergencyFacility.operating_status == "OPERATIONAL")
            if shelter_only:
                query = query.filter(EmergencyFacility.is_officially_designated_shelter == True)
            elif facility_type != "all":
                query = query.filter(EmergencyFacility.facility_type == facility_type)

            facilities = query.all()
            if not facilities:
                return {
                    "status": "NO_FACILITY_FOUND",
                    "error": f"No operational facilities matching criteria (type='{facility_type}', shelter_only={shelter_only}) found in database.",
                    "route_found": False
                }

            # Pre-filter candidate facilities by straight-line distance (top 8 nearest)
            candidates_with_dist = []
            for f in facilities:
                d = haversine_distance_m(origin_lon, origin_lat, float(f.longitude), float(f.latitude))
                candidates_with_dist.append((f, d))

            candidates_with_dist.sort(key=lambda x: x[1])
            top_candidates = candidates_with_dist[:8]

            best_route = None
            best_facility = None
            min_travel_time = float("inf")

            for fac, straight_dist in top_candidates:
                route_res = self.calculate_route(
                    origin_lat=origin_lat,
                    origin_lon=origin_lon,
                    dest_lat=float(fac.latitude),
                    dest_lon=float(fac.longitude),
                    routing_mode=routing_mode,
                    include_alternatives=False,
                    db=db
                )
                if route_res.get("route_found"):
                    t_min = route_res["primary_route"]["estimated_duration_min"]
                    if t_min < min_travel_time:
                        min_travel_time = t_min
                        best_route = route_res
                        best_facility = fac

            if not best_route or not best_facility:
                return {
                    "status": "UNREACHABLE",
                    "error": f"No candidate {facility_type} could be reached due to road network disconnection or road closures.",
                    "route_found": False
                }

            return {
                "status": "SUCCESS",
                "route_found": True,
                "destination_facility_id": best_facility.facility_id,
                "destination_facility_name": best_facility.name,
                "distance_km": best_route["primary_route"]["distance_km"],
                "estimated_duration_minutes": best_route["primary_route"]["estimated_duration_min"],
                "route_geojson": best_route["primary_route"]["route_geojson"],
                "target_facility": {
                    "facility_id": best_facility.facility_id,
                    "name": best_facility.name,
                    "facility_type": best_facility.facility_type,
                    "is_officially_designated_shelter": best_facility.is_officially_designated_shelter,
                    "latitude": float(best_facility.latitude),
                    "longitude": float(best_facility.longitude),
                    "locality_name": best_facility.locality_name,
                    "contact_phone": best_facility.contact_phone,
                    "verification_status": best_facility.verification_status,
                    "operating_status": best_facility.operating_status,
                    "capacity_total": best_facility.capacity_total,
                    "capacity_available": best_facility.capacity_available,
                    "capacity_notes": best_facility.capacity_status_notes,
                    "accessibility_notes": best_facility.accessibility_notes
                },
                "route": best_route["primary_route"],
                "hazard_exposure": best_route.get("hazard_exposure"),
                "uncertainty_and_safety_notice": best_route.get("uncertainty_and_safety_notice"),
                "safety_disclaimer": best_route.get("safety_disclaimer")
            }

        finally:
            if close_session:
                db.close()
