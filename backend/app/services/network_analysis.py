"""
Infrastructure Network Analysis Service (Model C)
Uses NetworkX to build a spatial routing graph of Mumbai's arterial transport network,
simulating edge failure, waterlogging cut-offs, Dijkstra emergency accessibility,
and facility disconnection metrics.
"""
import networkx as nx
import numpy as np
from typing import Dict, Any, List, Optional
import json
import os
from app.config import settings

class MumbaiNetworkAnalyzer:
    def __init__(self):
        self.G_base = nx.Graph()
        self._build_base_network()

    def _build_base_network(self):
        """
        Builds the foundational topological graph for Mumbai transport corridors
        and healthcare emergency nodes.
        """
        # Node coordinates: [lon, lat]
        nodes = {
            "NODE_SION_CIRCLE": {"pos": (72.860, 19.038), "name": "Sion Circle Hub", "ward": "MUM_WARD_FN_SION"},
            "NODE_KURLA_STN": {"pos": (72.880, 19.065), "name": "Kurla Station West", "ward": "MUM_WARD_L_KURLA"},
            "NODE_BKC_CENTRAL": {"pos": (72.864, 19.064), "name": "BKC Diamond Bourse", "ward": "MUM_WARD_HE_BANDRA_E"},
            "NODE_KALANAGAR": {"pos": (72.845, 19.058), "name": "Kalanagar Junction", "ward": "MUM_WARD_HE_BANDRA_E"},
            "NODE_BANDRA_W": {"pos": (72.830, 19.055), "name": "Bandra West Terminal", "ward": "MUM_WARD_HW_BANDRA_W"},
            "NODE_AIRPORT_T2": {"pos": (72.875, 19.095), "name": "Chhatrapati Shivaji Maharaj T2", "ward": "MUM_WARD_L_KURLA"},
            "NODE_ANDHERI_W": {"pos": (72.840, 19.115), "name": "Andheri West SV Road", "ward": "MUM_WARD_KW_ANDHERI_W"},
            "NODE_ANDHERI_E": {"pos": (72.865, 19.115), "name": "Andheri East MIDC", "ward": "MUM_WARD_KE_ANDHERI_E"},
            "NODE_GHATKOPAR": {"pos": (72.905, 19.085), "name": "Ghatkopar EEH Junction", "ward": "MUM_WARD_L_KURLA"},
            "NODE_MAHIM": {"pos": (72.840, 19.035), "name": "Mahim Causeway", "ward": "MUM_WARD_GN_DHARAVI"},
            "NODE_DADAR_TT": {"pos": (72.845, 19.018), "name": "Dadar TT Circle", "ward": "MUM_WARD_GS_WORLI"},
            "NODE_POWAI": {"pos": (72.905, 19.125), "name": "Powai Lake Junction", "ward": "MUM_WARD_S_POWAI"},
            # Critical Hospital Nodes
            "HOSP_SION": {"pos": (72.8601, 19.0384), "name": "Lokmanya Tilak Hospital (Sion)", "is_hospital": True},
            "HOSP_BHABHA_KURLA": {"pos": (72.8790, 19.0665), "name": "Bhabha Hospital (Kurla)", "is_hospital": True},
            "HOSP_BKC_ASIAN": {"pos": (72.8640, 19.0640), "name": "Asian Heart Institute (BKC)", "is_hospital": True},
            "HOSP_LILAVATI": {"pos": (72.8290, 19.0512), "name": "Lilavati Hospital (Bandra)", "is_hospital": True},
            "HOSP_NANAVATI": {"pos": (72.8415, 19.0988), "name": "Nanavati Hospital (Vile Parle)", "is_hospital": True},
            "HOSP_COOPER": {"pos": (72.8360, 19.1105), "name": "Cooper Hospital (Juhu)", "is_hospital": True}
        }

        for nid, data in nodes.items():
            self.G_base.add_node(nid, **data)

        # Edges: (u, v, length_km, baseline_speed_kmh, flood_vulnerability [0..1])
        edges = [
            ("NODE_SION_CIRCLE", "HOSP_SION", 0.3, 30.0, 0.40, "Sion Hospital Access"),
            ("NODE_SION_CIRCLE", "NODE_MAHIM", 2.4, 45.0, 0.50, "Sion-Mahim Link"),
            ("NODE_SION_CIRCLE", "NODE_KURLA_STN", 3.8, 35.0, 0.90, "LBS Marg Kurla Reach"), # Highly flood-prone
            ("NODE_SION_CIRCLE", "NODE_DADAR_TT", 2.5, 45.0, 0.30, "Ambedkar Road"),
            ("NODE_MAHIM", "NODE_DADAR_TT", 2.2, 40.0, 0.25, "Senapati Bapat Marg"),
            ("NODE_MAHIM", "NODE_KALANAGAR", 2.8, 50.0, 0.85, "Sion-Bandra Link Road"), # Creek overflow
            ("NODE_KALANAGAR", "NODE_BANDRA_W", 2.0, 40.0, 0.20, "Bandra Reclamation"),
            ("NODE_BANDRA_W", "HOSP_LILAVATI", 0.8, 30.0, 0.15, "Lilavati Access Way"),
            ("NODE_KALANAGAR", "NODE_BKC_CENTRAL", 2.1, 45.0, 0.45, "BKC Boulevard"),
            ("NODE_BKC_CENTRAL", "HOSP_BKC_ASIAN", 0.2, 30.0, 0.35, "Asian Heart Access"),
            ("NODE_BKC_CENTRAL", "NODE_KURLA_STN", 2.2, 35.0, 0.80, "BKC-Kurla SCLR Link"),
            ("NODE_KURLA_STN", "HOSP_BHABHA_KURLA", 0.5, 25.0, 0.95, "Belgrami Road"), # Chronic submersion
            ("NODE_KURLA_STN", "NODE_GHATKOPAR", 3.2, 45.0, 0.40, "LBS Ghatkopar Section"),
            ("NODE_GHATKOPAR", "NODE_POWAI", 5.0, 50.0, 0.25, "LBS to JVLR"),
            ("NODE_KURLA_STN", "NODE_AIRPORT_T2", 3.6, 40.0, 0.70, "Kurla-Andheri Link"),
            ("NODE_AIRPORT_T2", "NODE_ANDHERI_E", 2.5, 40.0, 0.45, "Sahar Airport Road"),
            ("NODE_KALANAGAR", "HOSP_NANAVATI", 4.8, 50.0, 0.35, "WEH to Vile Parle"),
            ("HOSP_NANAVATI", "NODE_ANDHERI_W", 2.4, 40.0, 0.40, "SV Road Vile Parle"),
            ("NODE_ANDHERI_W", "HOSP_COOPER", 1.2, 30.0, 0.50, "Juhu Vile Parle Link"),
            ("NODE_ANDHERI_W", "NODE_ANDHERI_E", 1.8, 20.0, 0.98, "Andheri Subway Choke Point"), # Severe subway flood
            ("NODE_ANDHERI_E", "NODE_POWAI", 4.2, 55.0, 0.30, "JVLR Corridor")
        ]

        for u, v, dist, speed, vuln, name in edges:
            time_hours = dist / speed
            self.G_base.add_edge(
                u, v,
                distance_km=dist,
                speed_kmh=speed,
                travel_time_min=round(time_hours * 60, 2),
                vulnerability=vuln,
                name=name
            )

    def analyze_accessibility(
        self,
        origin_coords: List[float],
        dest_facility_id: Optional[str] = None,
        rainfall_mm: float = 200.0,
        avoid_flooded: bool = True
    ) -> Dict[str, Any]:
        """
        Runs scenario-constrained route finding and calculates network disconnection.
        """
        # Find nearest graph node to user's origin
        origin_lon, origin_lat = origin_coords[0], origin_coords[1]
        nearest_node = None
        min_dist = float("inf")

        for n, data in self.G_base.nodes(data=True):
            if "pos" in data:
                plon, plat = data["pos"]
                d = np.hypot(origin_lon - plon, origin_lat - plat)
                if d < min_dist:
                    min_dist = d
                    nearest_node = n

        dest_node = "HOSP_BHABHA_KURLA"
        if dest_facility_id:
            # Map facility id to graph hospital node
            mapping_dict = {
                "INFRA_HOSP_01": "HOSP_SION",
                "INFRA_HOSP_02": "HOSP_BHABHA_KURLA",
                "INFRA_HOSP_03": "HOSP_BKC_ASIAN",
                "INFRA_HOSP_04": "HOSP_LILAVATI",
                "INFRA_HOSP_05": "HOSP_NANAVATI",
                "INFRA_HOSP_06": "HOSP_COOPER"
            }
            dest_node = mapping_dict.get(dest_facility_id, "HOSP_BHABHA_KURLA")

        # 1. Baseline Route (Dry Weather)
        try:
            baseline_path = nx.shortest_path(self.G_base, source=nearest_node, target=dest_node, weight="travel_time_min")
            baseline_dist = sum(self.G_base[u][v]["distance_km"] for u, v in zip(baseline_path[:-1], baseline_path[1:]))
            baseline_time = sum(self.G_base[u][v]["travel_time_min"] for u, v in zip(baseline_path[:-1], baseline_path[1:]))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            baseline_path = [nearest_node, dest_node]
            baseline_dist = 5.0
            baseline_time = 12.0

        # 2. Build Scenario Constrained Graph
        # Higher rainfall degrades speed and severs vulnerable segments
        G_scenario = self.G_base.copy()
        severed_edges = []
        degraded_edges = []

        flood_severity_factor = min(1.0, rainfall_mm / 300.0)

        for u, v, data in self.G_base.edges(data=True):
            vuln = data["vulnerability"]
            effective_risk = vuln * flood_severity_factor

            if effective_risk >= 0.70 and avoid_flooded:
                # Road segment is completely submerged / impassable
                G_scenario.remove_edge(u, v)
                severed_edges.append(data.get("name", f"{u}-{v}"))
            elif effective_risk >= 0.40:
                # Severe waterlogging: speed reduced to 8 km/h crawling speed
                degraded_speed = 8.0
                new_time = (data["distance_km"] / degraded_speed) * 60
                G_scenario[u][v]["travel_time_min"] = new_time
                degraded_edges.append(data.get("name", f"{u}-{v}"))

        # Find scenario route
        status = "ACCESSIBLE"
        scenario_path = []
        scenario_dist = baseline_dist
        scenario_time = baseline_time
        delay_min = 0.0

        try:
            scenario_path = nx.shortest_path(G_scenario, source=nearest_node, target=dest_node, weight="travel_time_min")
            scenario_dist = sum(self.G_base[u][v]["distance_km"] for u, v in zip(scenario_path[:-1], scenario_path[1:]))
            scenario_time = sum(G_scenario[u][v]["travel_time_min"] for u, v in zip(scenario_path[:-1], scenario_path[1:]))
            delay_min = max(0.0, scenario_time - baseline_time)
            if scenario_path != baseline_path:
                status = "DETOUR_REQUIRED"
        except nx.NetworkXNoPath:
            status = "SEVERED"
            scenario_path = baseline_path
            delay_min = 999.0
            advisory = f"CRITICAL: All direct vehicular corridors to {self.G_base.nodes[dest_node].get('name')} are severed by floodwaters ({', '.join(severed_edges[:2])}). Amphibious or high-clearance emergency transport required."
            return {
                "origin": origin_coords,
                "destination": list(self.G_base.nodes[dest_node]["pos"]),
                "destination_name": self.G_base.nodes[dest_node]["name"],
                "status": status,
                "baseline_distance_km": round(baseline_dist, 2),
                "scenario_distance_km": round(scenario_dist, 2),
                "delay_minutes": delay_min,
                "route_geometry": {
                    "type": "LineString",
                    "coordinates": [list(self.G_base.nodes[n]["pos"]) for n in scenario_path]
                },
                "traversed_segments": [self.G_base[u][v].get("name", "") for u, v in zip(scenario_path[:-1], scenario_path[1:])],
                "inundated_intersections_avoided": len(severed_edges),
                "advisory": advisory
            }

        # Build GeoJSON route LineString
        route_coords = [list(self.G_base.nodes[n]["pos"]) for n in scenario_path]

        advisory = (
            f"Route active via {len(scenario_path)-1} segments. "
            f"{'Detour active due to waterlogged LBS Marg/Subways.' if status == 'DETOUR_REQUIRED' else 'Normal clearance.'} "
            f"Estimated delay: +{round(delay_min, 1)} minutes."
        )

        return {
            "origin": origin_coords,
            "destination": list(self.G_base.nodes[dest_node]["pos"]),
            "destination_name": self.G_base.nodes[dest_node]["name"],
            "status": status,
            "baseline_distance_km": round(baseline_dist, 2),
            "scenario_distance_km": round(scenario_dist, 2),
            "delay_minutes": round(delay_min, 1),
            "route_geometry": {
                "type": "LineString",
                "coordinates": route_coords
            },
            "traversed_segments": [self.G_base[u][v].get("name", "") for u, v in zip(scenario_path[:-1], scenario_path[1:])],
            "inundated_intersections_avoided": len(severed_edges),
            "advisory": advisory
        }

network_analyzer = MumbaiNetworkAnalyzer()
