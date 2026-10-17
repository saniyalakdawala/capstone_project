import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  Route,
  Navigation,
  Building2,
  AlertTriangle,
  Hospital,
  Clock,
  ArrowRight
} from "lucide-react";
import { MapView } from "../components/MapView";
import {
  calculateEmergencyRoute,
  fetchRoadsGeoJSON,
  fetchInfrastructureGeoJSON,
  fetchWaterwaysGeoJSON,
  fetchRiskMapGeoJSON
} from "../services/api";

export const InfrastructureImpact: React.FC = () => {
  // Routing inputs
  const [origin, setOrigin] = useState<[number, number]>([72.845, 19.058]); // Kalanagar
  const [destFacility, setDestFacility] = useState("INFRA_HOSP_02"); // Bhabha Hospital Kurla
  const [avoidFlooded, setAvoidFlooded] = useState(true);
  const [routeResult, setRouteResult] = useState<any>(null);
  const [isRouting, setIsRouting] = useState(false);

  // Map Data
  const [roadsGeoJSON, setRoadsGeoJSON] = useState<any>(null);
  const [infraGeoJSON, setInfraGeoJSON] = useState<any>(null);
  const [waterwaysGeoJSON, setWaterwaysGeoJSON] = useState<any>(null);
  const [riskMapGeoJSON, setRiskMapGeoJSON] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      fetchRoadsGeoJSON(),
      fetchInfrastructureGeoJSON(),
      fetchWaterwaysGeoJSON(),
      fetchRiskMapGeoJSON("SCEN_HEAVY_200MM")
    ]).then(([roads, infra, waterways, risk]) => {
      setRoadsGeoJSON(roads);
      setInfraGeoJSON(infra);
      setWaterwaysGeoJSON(waterways);
      setRiskMapGeoJSON(risk);
    });
  }, []);

  const handleCalculateRoute = async () => {
    setIsRouting(true);
    try {
      const res = await calculateEmergencyRoute({
        origin: origin,
        destination_facility_id: destFacility,
        scenario_id: "SCEN_HEAVY_200MM",
        avoid_high_risk_roads: avoidFlooded
      });
      setRouteResult(res);
    } catch (err) {
      console.error("Routing error:", err);
    } finally {
      setIsRouting(false);
    }
  };

  // Run initial route calculation
  useEffect(() => {
    handleCalculateRoute();
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="bg-[#FFFCF6] border border-[#DDD4C5] rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold uppercase tracking-wider text-[#527C78]">
            Spatial Graph &amp; Network Analysis (Model C)
          </span>
          <span className="badge-normal text-[10px]">NetworkX Dijkstra Pathfinding</span>
        </div>
        <h1 className="serif-heading text-3xl font-bold text-[#343D38]">
          Infrastructure Exposure &amp; Emergency Reachability
        </h1>
        <p className="text-sm text-[#817B70] mt-1 max-w-3xl">
          Assess which hospitals and schools intersect predicted flood extents, and simulate how emergency vehicles can navigate around severed corridors (LBS Marg, Milan &amp; Andheri Subways, Sion-Bandra link road).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Interactive Routing Control Panel */}
        <div className="gis-surface space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#DDD4C5]">
            <h3 className="serif-heading text-lg font-bold text-[#343D38] flex items-center gap-1.5">
              <Navigation className="w-4 h-4 text-[#527C78]" />
              Emergency Route Finder
            </h3>
            <span className="badge-high text-[10px]">Flood Constrained</span>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#343D38] block mb-1">
              Dispatch Origin (Emergency Hub)
            </label>
            <select
              onChange={(e) => {
                const [lon, lat] = e.target.value.split(",").map(Number);
                setOrigin([lon, lat]);
              }}
              className="w-full bg-[#F5F0E6] border border-[#DDD4C5] rounded-lg p-2 text-xs font-medium text-[#343D38] focus:outline-none"
            >
              <option value="72.845,19.058">Kalanagar Junction (Bandra East Hub)</option>
              <option value="72.860,19.038">Sion Circle Response Station</option>
              <option value="72.875,19.095">Airport T2 Emergency Center</option>
              <option value="72.905,19.125">Powai Lake / JVLR Depot</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#343D38] block mb-1">
              Target Emergency Healthcare Facility
            </label>
            <select
              value={destFacility}
              onChange={(e) => setDestFacility(e.target.value)}
              className="w-full bg-[#F5F0E6] border border-[#DDD4C5] rounded-lg p-2 text-xs font-medium text-[#343D38] focus:outline-none"
            >
              <option value="INFRA_HOSP_02">Bhabha Hospital (Kurla West - High Risk)</option>
              <option value="INFRA_HOSP_01">Lokmanya Tilak Municipal Hospital (Sion)</option>
              <option value="INFRA_HOSP_03">Asian Heart Institute (BKC)</option>
              <option value="INFRA_HOSP_04">Lilavati Hospital (Bandra West)</option>
              <option value="INFRA_HOSP_05">Nanavati Max Super Speciality (Vile Parle)</option>
              <option value="INFRA_HOSP_06">Dr. R.N. Cooper Hospital (Juhu)</option>
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer text-xs text-[#343D38] pt-1">
            <input
              type="checkbox"
              checked={avoidFlooded}
              onChange={(e) => setAvoidFlooded(e.target.checked)}
              className="rounded accent-[#527C78]"
            />
            <span>Avoid Submerged &amp; Impassable Roads</span>
          </label>

          <button
            onClick={handleCalculateRoute}
            disabled={isRouting}
            className="w-full btn-primary justify-center py-2.5 text-xs"
          >
            {isRouting ? "Calculating Topological Route..." : "Compute Safe Emergency Corridor"}
          </button>

          {/* Route Result Card */}
          {routeResult && (
            <div className="mt-4 pt-4 border-t border-[#DDD4C5] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#817B70] uppercase">Route Status:</span>
                <span
                  className={
                    routeResult.status === "DETOUR_REQUIRED"
                      ? "badge-high"
                      : routeResult.status === "SEVERED"
                      ? "badge-critical"
                      : "badge-normal"
                  }
                >
                  {routeResult.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded bg-[#F5F0E6] border border-[#DDD4C5]">
                  <span className="text-[#817B70] text-[10px]">Normal Distance</span>
                  <div className="font-bold text-[#343D38]">{routeResult.baseline_distance_km} km</div>
                </div>
                <div className="p-2 rounded bg-[#F5F0E6] border border-[#DDD4C5]">
                  <span className="text-[#817B70] text-[10px]">Detour Distance</span>
                  <div className="font-bold text-[#C47B5A]">{routeResult.scenario_distance_km} km</div>
                </div>
              </div>

              <div className="p-2 rounded bg-[#F5F0E6] border border-[#DDD4C5] flex items-center justify-between text-xs">
                <span className="text-[#817B70] flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-[#527C78]" />
                  Estimated Flood Delay:
                </span>
                <span className="font-bold text-[#A7473F]">
                  +{routeResult.delay_minutes} min
                </span>
              </div>

              <p className="text-[11px] text-[#817B70] italic bg-[#FFFCF6] p-2 rounded border border-[#DDD4C5]">
                {routeResult.advisory}
              </p>
            </div>
          )}
        </div>

        {/* Right 2 Columns: Map with Active Route Highlight */}
        <div className="lg:col-span-2 space-y-4">
          <div className="gis-surface p-4">
            <h3 className="serif-heading text-lg font-bold text-[#343D38] mb-2">
              Topological Route Navigation &amp; Hazard Closures
            </h3>
            <MapView
              roadsGeoJSON={roadsGeoJSON}
              infraGeoJSON={infraGeoJSON}
              waterwaysGeoJSON={waterwaysGeoJSON}
              riskMapGeoJSON={riskMapGeoJSON}
              activeRoute={routeResult}
              height="420px"
            />
          </div>

          {/* Infrastructure Exposure Summary Table */}
          <div className="gis-surface">
            <h3 className="serif-heading text-lg font-bold text-[#343D38] mb-3">
              Ward-Level Critical Facility Exposure Audit
            </h3>
            <div className="overflow-x-auto text-xs">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-[#DDD4C5] text-[#817B70] font-semibold">
                    <th className="pb-2">Ward Identifier</th>
                    <th className="pb-2">Vulnerable Hospitals</th>
                    <th className="pb-2">Vulnerable Schools</th>
                    <th className="pb-2">Submerged Corridors</th>
                    <th className="pb-2">Topological Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#DDD4C5]/50 text-[#343D38]">
                  <tr>
                    <td className="py-2.5 font-semibold">Ward L (Kurla)</td>
                    <td className="py-2.5">Bhabha Municipal Hospital (350 Beds)</td>
                    <td className="py-2.5">Holy Cross High School</td>
                    <td className="py-2.5 text-[#A7473F]">LBS Marg, Kurla-Andheri Link</td>
                    <td className="py-2.5"><span className="badge-critical">ISOLATED</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5 font-semibold">Ward F/North (Sion)</td>
                    <td className="py-2.5">Sion Hospital (1400 Beds Trauma)</td>
                    <td className="py-2.5">Don Bosco High School</td>
                    <td className="py-2.5 text-[#C47B5A]">Ambedkar Road, Sion Circle</td>
                    <td className="py-2.5"><span className="badge-high">DETOUR REQUIRED</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5 font-semibold">Ward H/East (BKC)</td>
                    <td className="py-2.5">Asian Heart Institute (250 Beds)</td>
                    <td className="py-2.5">Dhirubhai Ambani School</td>
                    <td className="py-2.5 text-[#C47B5A]">BKC Connector, SCLR Link</td>
                    <td className="py-2.5"><span className="badge-high">DETOUR REQUIRED</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5 font-semibold">Ward K/West (Andheri W)</td>
                    <td className="py-2.5">Nanavati Max, Cooper Hospital</td>
                    <td className="py-2.5">Bhavan's College Campus</td>
                    <td className="py-2.5 text-[#A7473F]">Milan &amp; Andheri Subways</td>
                    <td className="py-2.5"><span className="badge-critical">CHOKE POINT</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
