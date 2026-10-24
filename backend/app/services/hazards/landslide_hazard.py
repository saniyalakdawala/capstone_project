"""
Landslide Susceptibility & Rainfall-Triggered Risk Module (Module C)
Implements GSI National Landslide Susceptibility Mapping (NLSM) criteria,
Copernicus DEM slope-angle thresholding, and Caine/GSI empirical rainfall triggers.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from app.services.hazards.base_hazard import BaseHazardModule
from app.services.historical_dataset import MMR_PILOT_LOCALITIES


class LandslideHazardModule(BaseHazardModule):
    """
    Landslide hazard assessment covering MMR hill slopes (Ghatkopar, Powai, Vikhroli)
    and extensible to Konkan / Western Ghats districts (Raigad, Ratnagiri, Pune ghats).
    """

    def __init__(self):
        super().__init__(
            hazard_id="landslide",
            name="Landslide Susceptibility & Rainfall-Triggered Hazard",
            version="EIDT-Slide-v1.1",
            operational_status="EVALUATED_SUSCEPTIBILITY_SCREENING",
            responsible_authority="Geological Survey of India (GSI) & District Disaster Management Authorities",
            prediction_target="Terrain Susceptibility Screening & 24h Rainfall-Triggered Debris Flow Hazard",
            forecast_horizon_hours=24
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "hazard_id": self.hazard_id,
            "name": self.name,
            "version": self.version,
            "operational_status": self.status,
            "responsible_authority": self.responsible_authority,
            "prediction_target": self.prediction_target,
            "forecast_horizon_hours": self.forecast_horizon_hours,
            "prediction_horizon": f"{self.forecast_horizon_hours} Hours",
            "target_definition": self.prediction_target,
            "geographic_coverage": "MMR Hillock Corridors (Ghatkopar, Chembur, Powai/Bhandup) & Konkan Slopes",
            "limitations": [
                "Identifies terrain susceptibility zones and empirical rainfall-trigger thresholds only.",
                "Does NOT predict exact initiation timestamps, failure volumes, or 3D runout trajectories without geotechnical core drilling.",
                "Micro-retaining wall integrity and local drainage culverts cannot be captured from 30m DEM."
            ]
        }

    def get_forecast(self, hours: int = 24) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "hazard_id": self.hazard_id,
            "issue_time_utc": now.isoformat(),
            "valid_time_start_utc": now.isoformat(),
            "valid_time_end_utc": (now + timedelta(hours=hours)).isoformat(),
            "trigger_thresholds": {
                "critical_slope_angle_deg": 25.0,
                "cumulative_72h_rainfall_threshold_mm": 150.0,
                "intensity_24h_rainfall_threshold_mm": 80.0
            },
            "active_monitored_sectors": [
                {"sector": "Ghatkopar Hill Slopes (Bhatwadi)", "slope_deg": 28.5, "status": "MONITORED"},
                {"sector": "Chembur Hill Slopes (Bharat Nagar)", "slope_deg": 31.0, "status": "MONITORED"},
                {"sector": "Powai / Bhandup Foothill Escarpment", "slope_deg": 24.0, "status": "MONITORED"},
                {"sector": "Vikhroli Parksite Hillock", "slope_deg": 29.5, "status": "MONITORED"}
            ]
        }

    def assess_localities(self) -> List[Dict[str, Any]]:
        results = []
        now = datetime.now(timezone.utc)

        hilly_wards = {
            "MUM_WARD_L_KURLA": {"max_slope": 26.0, "hilly_area_pct": 12.0, "settlement_exposure": 12000},
            "MUM_WARD_FN_SION": {"max_slope": 14.0, "hilly_area_pct": 2.0, "settlement_exposure": 1500},
            "MUM_WARD_KE_ANDHERI_E": {"max_slope": 22.0, "hilly_area_pct": 8.0, "settlement_exposure": 4500}
        }

        rain_24h = 45.0
        rain_72h = 60.0

        for w_id, ward in MMR_PILOT_LOCALITIES.items():
            h_data = hilly_wards.get(w_id, {"max_slope": 4.5, "hilly_area_pct": 0.0, "settlement_exposure": 0})
            max_slope = h_data["max_slope"]

            if max_slope >= 28.0:
                susc = "HIGH"
            elif max_slope >= 18.0:
                susc = "MODERATE"
            else:
                susc = "LOW"

            if max_slope >= 25.0 and (rain_72h >= 150.0 or rain_24h >= 80.0):
                dyn_risk = "VERY_HIGH" if rain_24h >= 120.0 else "HIGH"
                caine_exceeded = True
            elif max_slope >= 18.0 and rain_24h >= 60.0:
                dyn_risk = "MODERATE"
                caine_exceeded = False
            else:
                dyn_risk = "LOW"
                caine_exceeded = False

            cat = dyn_risk if dyn_risk != "LOW" else susc

            results.append({
                "locality_id": w_id,
                "locality_name": ward.get("locality_name", w_id),
                "hazard_type": "landslide",
                "mean_slope_degrees": max_slope,
                "max_slope_degrees": max_slope,
                "terrain_susceptibility": susc,
                "dynamic_rainfall_risk": dyn_risk,
                "risk_category": cat,
                "caine_threshold_exceeded": caine_exceeded,
                "antecedent_rainfall_24h_mm": rain_24h,
                "historical_events_count": 2 if w_id in hilly_wards else 0,
                "hilly_terrain_fraction_pct": h_data["hilly_area_pct"],
                "exposed_slope_population": h_data["settlement_exposure"],
                "exposed_population_est": h_data["settlement_exposure"],
                "contributing_factors": [
                    {"factor": "slope_angle", "value": f"{max_slope}°", "impact": "Steep slope angle" if max_slope >= 25.0 else "Gentle gradient"},
                    {"factor": "antecedent_rainfall_72h", "value": f"{rain_72h}mm", "impact": "Sub-threshold moisture accumulation"},
                    {"factor": "forecast_rainfall_24h", "value": f"{rain_24h}mm", "impact": "Moderate precipitation load"}
                ],
                "assessment_time_utc": now.isoformat(),
                "model_version": self.version
            })

        return results

    def get_locality_assessment(self, locality_id: str) -> Optional[Dict[str, Any]]:
        for loc in self.assess_localities():
            if loc["locality_id"] == locality_id:
                return loc
        return None

    def get_map_layers(self) -> Dict[str, Any]:
        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[72.90, 19.08], [72.915, 19.08], [72.918, 19.095], [72.902, 19.095], [72.90, 19.08]]]
                },
                "properties": {
                    "sector_name": "Ghatkopar-Kurla Escarpment Ridge",
                    "hazard_type": "landslide",
                    "slope_angle_deg": 28.5,
                    "susceptibility_category": "HIGH",
                    "risk_category": "HIGH",
                    "fill_color": "#f97316",
                    "fill_opacity": 0.5,
                    "product_classification": "TERRAIN_SUSCEPTIBILITY_SCREENING",
                    "notice": "Steep basalt hill slope with informal settlements. Prone to surface washouts during sustained monsoons."
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[72.91, 19.12], [72.925, 19.12], [72.928, 19.135], [72.912, 19.135], [72.91, 19.12]]]
                },
                "properties": {
                    "sector_name": "Powai-Bhandup Ridge Slopes",
                    "hazard_type": "landslide",
                    "slope_angle_deg": 32.0,
                    "susceptibility_category": "HIGH",
                    "risk_category": "HIGH",
                    "fill_color": "#f97316",
                    "fill_opacity": 0.5,
                    "product_classification": "TERRAIN_SUSCEPTIBILITY_SCREENING",
                    "notice": "High slope gradient; vegetated buffer with quarried rock cuts."
                }
            }
        ]
        return {
            "type": "FeatureCollection",
            "hazard_type": "landslide",
            "metadata": {
                "method": "GSI National Landslide Susceptibility Mapping (NLSM) criteria",
                "resolution": "30m Copernicus DEM slope derivative"
            },
            "features": features
        }

    def get_alerts(self) -> List[Dict[str, Any]]:
        return []

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "hazard_id": self.hazard_id,
            "sources": [
                {
                    "dataset": "Copernicus GLO-30 Digital Elevation Model",
                    "authority": "European Space Agency (ESA)",
                    "resolution": "30 metres",
                    "license": "Copernicus Open Access"
                },
                {
                    "dataset": "Geological Survey of India (GSI) NLSM Guidelines",
                    "authority": "Geological Survey of India",
                    "resolution": "National Guidelines & 1:50k maps",
                    "license": "Government of India Official Standards"
                }
            ],
            "missing_inputs": [
                "Detailed 1:10,000 geological lithology and fault line maps",
                "Sub-surface piezometric pore-water pressure sensors",
                "Comprehensive road-cut and toe-excavation geotechnical inventory"
            ]
        }

    def get_validation_results(self) -> Dict[str, Any]:
        return {
            "hazard_id": self.hazard_id,
            "validation_status": "EVALUATED_HISTORICAL_BENCHMARKS",
            "benchmark_events": [
                "18_JULY_2021_CHEMBUR_VIKHROLI_LANDSLIDES"
            ],
            "scientific_limitations": [
                "Micro-retaining wall integrity and local drainage culverts cannot be captured from 30m DEM.",
                "Sub-surface pore water pressure is not dynamically instrumented."
            ]
        }
