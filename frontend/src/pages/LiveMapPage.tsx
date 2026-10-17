import React, { useEffect, useState } from "react";
import { MapView } from "../components/MapView";
import { FeatureInspector, SelectedFeature } from "../components/FeatureInspector";
import {
  fetchStudyAreasGeoJSON,
  fetchWaterwaysGeoJSON,
  fetchRoadsGeoJSON,
  fetchInfrastructureGeoJSON,
  fetchRiskMapGeoJSON,
  fetchFloodEventsGeoJSON,
  fetchScenarios,
  fetchOSMStatus
} from "../services/api";
import { Search, Filter, AlertCircle, Compass, Info, CheckCircle2, Layers } from "lucide-react";

interface LiveMapPageProps {
  selectedWard: string;
  setSelectedWard: (ward: string) => void;
}

export const LiveMapPage: React.FC<LiveMapPageProps> = ({ selectedWard, setSelectedWard }) => {
  const [wardsGeoJSON, setWardsGeoJSON] = useState<any>(null);
  const [waterwaysGeoJSON, setWaterwaysGeoJSON] = useState<any>(null);
  const [roadsGeoJSON, setRoadsGeoJSON] = useState<any>(null);
  const [infraGeoJSON, setInfraGeoJSON] = useState<any>(null);
  const [riskMapGeoJSON, setRiskMapGeoJSON] = useState<any>(null);
  const [historicalGeoJSON, setHistoricalGeoJSON] = useState<any>(null);
  const [osmStatus, setOsmStatus] = useState<any>(null);
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("SCEN_HEAVY_200MM");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeature | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMapData = async () => {
      try {
        const [wards, waterways, roads, infra, risk, hist, scList, osm] = await Promise.all([
          fetchStudyAreasGeoJSON(),
          fetchWaterwaysGeoJSON(),
          fetchRoadsGeoJSON(),
          fetchInfrastructureGeoJSON(),
          fetchRiskMapGeoJSON(selectedScenarioId),
          fetchFloodEventsGeoJSON(),
          fetchScenarios(),
          fetchOSMStatus()
        ]);
        setWardsGeoJSON(wards);
        setWaterwaysGeoJSON(waterways);
        setRoadsGeoJSON(roads);
        setInfraGeoJSON(infra);
        setRiskMapGeoJSON(risk);
        setHistoricalGeoJSON(hist);
        setScenarios(scList);
        setOsmStatus(osm);
      } catch (err) {
        console.error("Error loading map data:", err);
      } finally {
        setLoading(false);
      }
    };
    loadMapData();
  }, [selectedScenarioId]);

  return (
    <div className="space-y-4">
      {/* Real Data Provenance Banner */}
      <div className="gis-surface px-4 py-2.5 flex flex-col md:flex-row md:items-center justify-between text-xs gap-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#527C78] shrink-0" />
          <span className="text-[#343D38]">
            <strong className="text-[#527C78]">Production GIS Integration:</strong> OpenStreetMap Mumbai Pilot &bull; <b>{roadsGeoJSON?.features?.length?.toLocaleString() || "6,768"}</b> Real Roads &bull; <b>{infraGeoJSON?.features?.length || "22"}</b> Facilities &bull; <b>{waterwaysGeoJSON?.features?.length || "14"}</b> Waterways
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-[#817B70]">
          <span>CRS: <b className="text-[#343D38]">EPSG:4326</b></span>
          <span>&bull;</span>
          <span>Store: <b className="text-[#343D38]">PostgreSQL &amp; GPKG</b></span>
          <span>&bull;</span>
          <span>&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline hover:text-[#527C78]">OpenStreetMap contributors</a></span>
        </div>
      </div>

      {/* Map Control & Filter Bar */}
      <div className="gis-surface p-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Left: Ward & Location Search */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#817B70]" />
            <input
              type="text"
              placeholder="Filter road/place (e.g. Kurla, BKC)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-[#EEE7DA]/50 border border-[#DDD4C5] rounded-md text-xs text-[#343D38] focus:outline-none w-52 font-medium"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-[#817B70] font-medium">Study Ward:</span>
            <select
              value={selectedWard}
              onChange={(e) => setSelectedWard(e.target.value)}
              className="bg-[#EEE7DA]/70 border border-[#DDD4C5] rounded-md px-2.5 py-1.5 text-xs font-semibold text-[#343D38] focus:outline-none cursor-pointer"
            >
              <option value="MUM_WARD_L_KURLA">Ward L (Kurla - Sakinaka)</option>
              <option value="MUM_WARD_FN_SION">Ward F/North (Sion - Matunga)</option>
              <option value="MUM_WARD_HE_BANDRA_E">Ward H/East (Bandra East - BKC)</option>
              <option value="MUM_WARD_GN_DHARAVI">Ward G/North (Dharavi - Mahim)</option>
              <option value="MUM_WARD_KW_ANDHERI_W">Ward K/West (Andheri - Juhu)</option>
              <option value="MUMBAI_ALL">Greater Mumbai Extent</option>
            </select>
          </div>
        </div>

        {/* Right: Active Scenario Overlay Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[#817B70]">Scenario Inundation Model:</span>
          <select
            value={selectedScenarioId}
            onChange={(e) => setSelectedScenarioId(e.target.value)}
            className="bg-[#EEE7DA]/70 border border-[#DDD4C5] rounded-md px-3 py-1.5 text-xs font-bold text-[#A7473F] focus:outline-none cursor-pointer"
          >
            {scenarios.map((sc) => (
              <option key={sc.scenario_id} value={sc.scenario_id}>
                {sc.scenario_name} ({sc.rainfall_total_mm} mm)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Full-Size Map Workspace with Contextual Feature Inspector Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Full Interactive Map View */}
        <div className={`${selectedFeature ? "lg:col-span-8" : "lg:col-span-12"} transition-all duration-300`}>
          <MapView
            wardsGeoJSON={wardsGeoJSON}
            waterwaysGeoJSON={waterwaysGeoJSON}
            roadsGeoJSON={roadsGeoJSON}
            infraGeoJSON={infraGeoJSON}
            riskMapGeoJSON={riskMapGeoJSON}
            historicalGeoJSON={historicalGeoJSON}
            height="620px"
            selectedWardId={selectedWard}
            onSelectFeature={(feat) => setSelectedFeature(feat)}
            selectedFeatureId={selectedFeature?.id}
          />
        </div>

        {/* Feature Details Side Drawer (when feature clicked) */}
        {selectedFeature && (
          <div className="lg:col-span-4 space-y-3">
            <FeatureInspector
              feature={selectedFeature}
              onClose={() => setSelectedFeature(null)}
            />
          </div>
        )}
      </div>

      {/* Cartographic Metadata Bar */}
      <div className="gis-surface p-3 text-xs text-[#817B70] flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-[#527C78] shrink-0" />
          <span>
            <b>Cartographic Projection:</b> WGS84 (EPSG:4326) &bull; Projected: UTM Zone 43N (EPSG:32643) &bull; Elevation Datum: EGM96 Copernicus 30m.
          </span>
        </div>
        <span className="text-[#343D38] font-semibold text-xs whitespace-nowrap">
          Astronomical High Tide Reference: 4.10m MSL
        </span>
      </div>
    </div>
  );
};
