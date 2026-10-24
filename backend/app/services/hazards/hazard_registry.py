"""
Central Hazard Module Registry (Phase 3)
Coordinates all 6 hazard categories across Maharashtra Digital Twin:
1. Flooding (flood)
2. Heatwaves & Urban Heat Stress (heatwave)
3. Landslides (landslide)
4. Drought & Water Scarcity (drought)
5. Coastal Inundation & Marine Conditions (coastal)
6. Severe Thunderstorms, Lightning & Damaging Winds (thunderstorm)
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.hazards.base_hazard import BaseHazardModule
from app.services.hazards.flood_hazard import FloodHazardModule
from app.services.hazards.heatwave_hazard import HeatwaveHazardModule
from app.services.hazards.landslide_hazard import LandslideHazardModule
from app.services.hazards.drought_hazard import DroughtHazardModule
from app.services.hazards.coastal_hazard import CoastalHazardModule
from app.services.hazards.thunderstorm_hazard import ThunderstormHazardModule
from app.services.hazards.alert_manager import AlertLifecycleManager


class HazardRegistry:
    def __init__(self):
        self.modules: Dict[str, BaseHazardModule] = {
            "flood": FloodHazardModule(),
            "heatwave": HeatwaveHazardModule(),
            "landslide": LandslideHazardModule(),
            "drought": DroughtHazardModule(),
            "coastal": CoastalHazardModule(),
            "thunderstorm": ThunderstormHazardModule()
        }
        self.alert_manager = AlertLifecycleManager()

    def list_hazards(self) -> List[Dict[str, Any]]:
        """Lists all registered hazard modules with operational status."""
        return [mod.build_meta_summary() for mod in self.modules.values()]

    def get_module(self, hazard_id: str) -> Optional[BaseHazardModule]:
        """Retrieves a specific hazard module by identifier."""
        return self.modules.get(hazard_id.lower().strip())

    def get_all_active_alerts(self, db: Session) -> List[Dict[str, Any]]:
        """Aggregates and synchronizes active alerts across all hazards."""
        # 1. Sync module candidate alerts into database via AlertLifecycleManager
        for h_id, mod in self.modules.items():
            mod_alerts = mod.get_alerts()
            for al in mod_alerts:
                self.alert_manager.register_or_update_alert(
                    db=db,
                    hazard_type=h_id,
                    geographic_scope=al.get("geographic_scope", "Maharashtra"),
                    severity_level=al.get("severity_level", "ADVISORY"),
                    headline=al.get("headline", f"{mod.name} Advisory"),
                    description=al.get("description", ""),
                    issuing_authority=al.get("issuing_authority", mod.responsible_authority),
                    is_official_warning=al.get("is_official_warning", False),
                    recommended_action=al.get("recommended_action", "Monitor official channels."),
                    rationale=al.get("rationale"),
                    study_area_id=al.get("study_area_id"),
                    duration_hours=24,
                    evidence_data=al.get("evidence_data"),
                    model_version=mod.version
                )

        # 2. Return all unexpired active alerts from database
        return self.alert_manager.get_active_alerts(db=db)


# Global singleton instance
hazard_registry = HazardRegistry()
