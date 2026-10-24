"""
Emergency Facilities & Active Road Restrictions API Router (Phase 4)
Provides traceable directory of hospitals, fire stations, officially designated shelters,
and verified road closures.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import math

from app.database import get_db
from app.models.schema import EmergencyFacility, RoadRestriction

router = APIRouter(prefix="/emergency", tags=["Emergency Facilities & Restrictions (Phase 4)"])


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


@router.get("/facilities")
def list_emergency_facilities(
    facility_type: Optional[str] = Query(None, description="hospital, evacuation_shelter, fire_station, police_station, relief_centre"),
    ward_id: Optional[str] = Query(None, description="Filter by study_area_id (e.g. MUM_WARD_L_KURLA)"),
    shelter_only: bool = Query(False, description="Filter strictly to officially designated evacuation shelters"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Returns verified emergency facilities and shelters with operating status,
    capacity notes, and official designations.
    """
    query = db.query(EmergencyFacility)
    if shelter_only:
        query = query.filter(EmergencyFacility.is_officially_designated_shelter == True)
    elif facility_type:
        query = query.filter(EmergencyFacility.facility_type == facility_type)

    if ward_id:
        query = query.filter(EmergencyFacility.ward_id == ward_id)

    facilities = query.limit(limit).all()

    return {
        "total_count": len(facilities),
        "count": len(facilities),
        "shelter_only_filter": shelter_only,
        "facilities": [
            {
                "facility_id": f.facility_id,
                "name": f.name,
                "facility_type": f.facility_type,
                "latitude": float(f.latitude),
                "longitude": float(f.longitude),
                "locality_name": f.locality_name,
                "ward_id": f.ward_id,
                "is_officially_designated_shelter": f.is_officially_designated_shelter,
                "verification_status": f.verification_status,
                "operating_status": f.operating_status,
                "contact_phone": f.contact_phone,
                "capacity_total": f.capacity_total,
                "capacity_available": f.capacity_available,
                "capacity_status_notes": f.capacity_status_notes,
                "accessibility_notes": f.accessibility_notes,
                "source_name": f.source_name
            }
            for f in facilities
        ]
    }


@router.get("/facilities/nearby")
def find_nearby_facilities(
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0),
    radius_km: float = Query(5.0, ge=0.1, le=50.0),
    facility_type: Optional[str] = Query(None),
    shelter_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Finds verified facilities within a specified geographical radius of coordinate.
    """
    actual_lat = lat if lat is not None else latitude
    actual_lon = lon if lon is not None else longitude
    if actual_lat is None or actual_lon is None:
        raise HTTPException(status_code=400, detail="Coordinates (latitude and longitude) are required.")

    query = db.query(EmergencyFacility).filter(EmergencyFacility.operating_status == "OPERATIONAL")
    if shelter_only or facility_type == "shelter":
        query = query.filter(EmergencyFacility.is_officially_designated_shelter == True)
    elif facility_type:
        query = query.filter(EmergencyFacility.facility_type == facility_type)

    all_facs = query.all()
    results = []

    for f in all_facs:
        d = haversine_km(actual_lon, actual_lat, float(f.longitude), float(f.latitude))
        if d <= radius_km:
            results.append({
                "facility_id": f.facility_id,
                "name": f.name,
                "facility_type": f.facility_type,
                "latitude": float(f.latitude),
                "longitude": float(f.longitude),
                "distance_km": round(d, 2),
                "is_officially_designated_shelter": f.is_officially_designated_shelter,
                "contact_phone": f.contact_phone,
                "capacity_available": f.capacity_available,
                "capacity_notes": f.capacity_status_notes
            })

    results.sort(key=lambda x: x["distance_km"])
    matched = results[:limit]
    return {
        "search_origin": {"latitude": actual_lat, "longitude": actual_lon},
        "search_radius_km": radius_km,
        "total_count": len(matched),
        "count": len(matched),
        "facilities": matched
    }


@router.get("/facilities/{facility_id}")
def get_facility_details(facility_id: str, db: Session = Depends(get_db)):
    """
    Retrieves full verified record for a specific emergency facility or shelter.
    """
    fac = db.query(EmergencyFacility).filter(EmergencyFacility.facility_id == facility_id).first()
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency facility '{facility_id}' not found in verified registry."
        )

    return {
        "facility_id": fac.facility_id,
        "source_id": fac.source_id,
        "source_name": fac.source_name,
        "name": fac.name,
        "facility_type": fac.facility_type,
        "latitude": float(fac.latitude),
        "longitude": float(fac.longitude),
        "locality_name": fac.locality_name,
        "ward_id": fac.ward_id,
        "verification_status": fac.verification_status,
        "operating_status": fac.operating_status,
        "contact_phone": fac.contact_phone,
        "capacity_total": fac.capacity_total,
        "capacity_available": fac.capacity_available,
        "capacity_status_notes": fac.capacity_status_notes,
        "is_officially_designated_shelter": fac.is_officially_designated_shelter,
        "accessibility_notes": fac.accessibility_notes,
        "provenance_url": fac.provenance_url,
        "last_verified_at": fac.last_verified_at.isoformat() if fac.last_verified_at else None
    }


@router.get("/restrictions")
def list_active_road_restrictions(
    include_hypothetical: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Returns active verified road closures, waterlogging blockages, and traffic restrictions.
    """
    query = db.query(RoadRestriction).filter(RoadRestriction.is_active == True)
    if not include_hypothetical:
        query = query.filter(RoadRestriction.is_hypothetical_scenario == False)

    restrictions = query.all()
    return {
        "total_count": len(restrictions),
        "count": len(restrictions),
        "restrictions": [
            {
                "restriction_id": r.restriction_id,
                "road_name": r.road_name,
                "road_segment_id": r.road_segment_id,
                "restriction_type": r.restriction_type,
                "severity": r.severity,
                "cause_description": r.cause_description,
                "issuing_authority": r.issuing_authority,
                "is_hypothetical_scenario": r.is_hypothetical_scenario,
                "valid_from": r.valid_from.isoformat() if r.valid_from else None,
                "valid_until": r.valid_until.isoformat() if r.valid_until else None
            }
            for r in restrictions
        ]
    }
