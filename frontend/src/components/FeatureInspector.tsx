import React from "react";
import {
  X,
  Compass,
  AlertTriangle,
  Info,
  ShieldCheck,
  Activity,
  Layers,
  MapPin,
  ExternalLink
} from "lucide-react";

export interface SelectedFeature {
  id: string;
  name: string;
  type: "road" | "facility" | "waterway" | "risk_zone";
  properties: Record<string, any>;
}

interface FeatureInspectorProps {
  feature: SelectedFeature | null;
  onClose: () => void;
}

export const FeatureInspector: React.FC<FeatureInspectorProps> = ({ feature, onClose }) => {
  if (!feature) return null;

  const p = feature.properties || {};
  const isRoad = feature.type === "road";
  const isFacility = feature.type === "facility";
  const vuln = parseFloat(p.vulnerability_index || 0);

  // Determine scientific risk classification
  let riskClass = "Low Susceptibility";
  let riskColor = "text-[#527C78]";
  let riskBg = "bg-[#527C78]/10 border-[#527C78]/25";
  if (vuln >= 0.8) {
    riskClass = "Critical Flood Susceptibility";
    riskColor = "text-[#A7473F]";
    riskBg = "bg-[#A7473F]/10 border-[#A7473F]/25";
  } else if (vuln >= 0.5) {
    riskClass = "High Inundation Risk";
    riskColor = "text-[#C47B5A]";
    riskBg = "bg-[#C47B5A]/10 border-[#C47B5A]/25";
  } else if (vuln >= 0.3) {
    riskClass = "Moderate Risk";
    riskColor = "text-[#D4A373]";
    riskBg = "bg-[#D4A373]/10 border-[#D4A373]/25";
  }

  return (
    <div className="bg-[#FFFCF6] border border-[#DDD4C5] rounded-xl p-4 shadow-sm text-xs space-y-3 animate-in fade-in duration-200">
      {/* Header with Title and Close Button */}
      <div className="flex items-start justify-between pb-2.5 border-b border-[#DDD4C5]/70">
        <div>
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="badge-predicted text-[10px]">
              {isRoad ? "Statistical Model Classification" : isFacility ? "Observed Critical Asset" : "Hydrographic Feature"}
            </span>
            <span className="text-[10px] text-[#817B70] font-mono">
              {feature.id || p.id || "OSM_FEATURE"}
            </span>
          </div>
          <h3 className="serif-heading text-lg font-bold text-[#343D38] leading-tight">
            {p.name || feature.name || (isRoad ? "Mumbai Transport Corridor" : "Geospatial Entity")}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-[#817B70] hover:text-[#343D38] p-1 rounded-md hover:bg-[#EEE7DA] transition-colors"
          title="Close Feature Details"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Primary Classification Badge Box */}
      <div className={`p-2.5 rounded-lg border ${riskBg} flex items-center justify-between`}>
        <div>
          <span className="text-[10px] uppercase font-bold tracking-wider text-[#817B70] block">
            Hazard Classification
          </span>
          <span className={`font-bold text-sm ${riskColor}`}>
            {riskClass}
          </span>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-[#817B70] block">Vulnerability Score</span>
          <span className="font-mono font-bold text-sm text-[#343D38]">
            {vuln.toFixed(2)} / 1.00
          </span>
        </div>
      </div>

      {/* Structured Key Attributes Table */}
      <div className="grid grid-cols-2 gap-2 text-[11px] text-[#343D38]">
        {isRoad && (
          <>
            <div className="bg-[#EEE7DA]/50 p-2 rounded border border-[#DDD4C5]/60">
              <span className="text-[#817B70] block text-[10px]">Highway Class</span>
              <span className="font-semibold capitalize text-[#527C78]">{p.road_class || "Residential"}</span>
            </div>
            <div className="bg-[#EEE7DA]/50 p-2 rounded border border-[#DDD4C5]/60">
              <span className="text-[#817B70] block text-[10px]">Segment Length</span>
              <span className="font-semibold">{Math.round(p.length_meters || 120)} meters</span>
            </div>
            <div className="bg-[#EEE7DA]/50 p-2 rounded border border-[#DDD4C5]/60">
              <span className="text-[#817B70] block text-[10px]">Speed Limit</span>
              <span className="font-semibold">{p.speed_kmh || 40} km/h</span>
            </div>
            <div className="bg-[#EEE7DA]/50 p-2 rounded border border-[#DDD4C5]/60">
              <span className="text-[#817B70] block text-[10px]">Forecast Horizon</span>
              <span className="font-semibold">+24h Scenario Run</span>
            </div>
          </>
        )}

        {isFacility && (
          <>
            <div className="bg-[#EEE7DA]/50 p-2 rounded border border-[#DDD4C5]/60">
              <span className="text-[#817B70] block text-[10px]">Facility Type</span>
              <span className="font-semibold capitalize text-[#527C78]">{p.feature_type || "Hospital"}</span>
            </div>
            <div className="bg-[#EEE7DA]/50 p-2 rounded border border-[#DDD4C5]/60">
              <span className="text-[#817B70] block text-[10px]">Operator</span>
              <span className="font-semibold">{p.operator || "Public / BMC"}</span>
            </div>
          </>
        )}
      </div>

      {/* Model Provenance & Supporting Terrain */}
      <div className="space-y-1.5 pt-1 text-[11px] text-[#817B70]">
        <div className="flex items-center justify-between">
          <span>Terrain &amp; Hydrology Datum:</span>
          <span className="text-[#343D38] font-medium">Copernicus GLO-30 / EGM96</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Model Architecture:</span>
          <span className="text-[#527C78] font-semibold">Random Forest v1.4 (AUC: 0.914)</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Data Source:</span>
          <span className="text-[#343D38]">{p.source || "OpenStreetMap (Live OSMnx)"}</span>
        </div>
      </div>

      {/* Mandatory Scientific Disclaimer (Section 5 Requirement) */}
      <div className="bg-[#F5F0E6] p-2.5 rounded-lg border border-[#DDD4C5] text-[10.5px] text-[#817B70] leading-relaxed flex items-start gap-2">
        <Info className="w-3.5 h-3.5 text-[#527C78] shrink-0 mt-0.5" />
        <p>
          <strong className="text-[#343D38]">Classification Protocol:</strong> Susceptibility score is derived statistically from topography, land imperviousness, and stormwater channel proximity. <em>This is an empirical vulnerability metric and does NOT represent confirmed active road closure or standing water.</em>
        </p>
      </div>
    </div>
  );
};
