import React, { useState, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Marker,
  Popup,
  Polyline,
  ScaleControl,
  useMap
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  Layers,
  Eye,
  EyeOff,
  Maximize2,
  Minimize2,
  Info,
  Compass,
  Map as MapIcon,
  Search,
  CheckCircle2
} from "lucide-react";
import { SelectedFeature } from "./FeatureInspector";

// Fix default leaflet marker icon issue in Vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png"
});

// Custom SVG Markers
const createMarkerIcon = (color: string) => {
  return L.divIcon({
    className: "custom-leaflet-marker",
    html: `<div style="background-color: ${color}; width: 13px; height: 13px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 4px rgba(0,0,0,0.35);"></div>`,
    iconSize: [13, 13],
    iconAnchor: [6.5, 6.5]
  });
};

const hospitalIcon = createMarkerIcon("#A7473F");
const schoolIcon = createMarkerIcon("#527C78");
const fireIcon = createMarkerIcon("#C47B5A");

// Helper component that invalidates map size when layout changes
const MapResizeHandler: React.FC<{ isFullscreen: boolean }> = ({ isFullscreen }) => {
  const map = useMap();
  useEffect(() => {
    const handleResize = () => {
      map.invalidateSize();
    };
    window.addEventListener("resize", handleResize);
    const t = setTimeout(handleResize, 150);
    return () => {
      window.removeEventListener("resize", handleResize);
      clearTimeout(t);
    };
  }, [map, isFullscreen]);
  return null;
};

export interface LayerRegistryItem {
  id: string;
  name: string;
  category: "Boundaries" | "Infrastructure" | "Hazard" | "Hydrology" | "Historical";
  dataType: "Observed" | "Predicted" | "Simulated";
  source: string;
  count?: number;
  visible: boolean;
}

interface MapViewProps {
  wardsGeoJSON?: any;
  waterwaysGeoJSON?: any;
  roadsGeoJSON?: any;
  infraGeoJSON?: any;
  riskMapGeoJSON?: any;
  historicalGeoJSON?: any;
  activeRoute?: any;
  height?: string;
  selectedWardId?: string;
  onSelectFeature?: (feature: SelectedFeature) => void;
  selectedFeatureId?: string;
}

export const MapView: React.FC<MapViewProps> = ({
  wardsGeoJSON,
  waterwaysGeoJSON,
  roadsGeoJSON,
  infraGeoJSON,
  riskMapGeoJSON,
  historicalGeoJSON,
  activeRoute,
  height = "560px",
  selectedWardId,
  onSelectFeature,
  selectedFeatureId
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [basemap, setBasemap] = useState<"google_streets" | "google_satellite" | "google_terrain" | "osm">("google_streets");
  const [showLayerPanel, setShowLayerPanel] = useState(true);

  // Google Maps API Key from Vite environment or build define
  const googleApiKey =
    (import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string) ||
    (typeof __GOOGLE_MAPS_KEY__ !== "undefined" ? __GOOGLE_MAPS_KEY__ : "") ||
    "";

  // Initialize official Google Maps JavaScript API SDK if key is provided
  useEffect(() => {
    if (googleApiKey && !document.getElementById("google-maps-js-sdk")) {
      const script = document.createElement("script");
      script.id = "google-maps-js-sdk";
      script.src = `https://maps.googleapis.com/maps/api/js?key=${googleApiKey}&libraries=places,geometry`;
      script.async = true;
      document.head.appendChild(script);
    }
  }, [googleApiKey]);

  // Layer visibility state
  const [layers, setLayers] = useState({
    wards: true,
    waterways: true,
    riskZones: true,
    roads: true,
    facilities: true,
    historical: false
  });

  const toggleLayer = (layerKey: keyof typeof layers) => {
    setLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  // Styling for Administrative Wards
  const wardStyle = (feature: any) => {
    const isSelected = selectedWardId && feature?.properties?.study_area_id === selectedWardId;
    return {
      fillColor: isSelected ? "#527C78" : "#A3B18A",
      weight: isSelected ? 2.5 : 1.2,
      opacity: 0.9,
      color: isSelected ? "#343D38" : "#6E7A6E",
      fillOpacity: isSelected ? 0.35 : 0.12
    };
  };

  // Styling for Risk Zones
  const riskStyle = (feature: any) => {
    const category = feature?.properties?.risk_category;
    let color = "#C47B5A";
    if (category === "CRITICAL") color = "#A7473F";
    else if (category === "MODERATE") color = "#D4A373";

    return {
      fillColor: color,
      weight: 1.5,
      opacity: 0.95,
      color: color,
      fillOpacity: 0.45,
      dashArray: "3, 4"
    };
  };

  // Styling for Road Network Segments
  const roadStyle = (feature: any) => {
    const isSelected = selectedFeatureId && (feature?.properties?.id === selectedFeatureId || feature?.id === selectedFeatureId);
    const vuln = parseFloat(feature?.properties?.vulnerability_index || 0);

    let color = "#527C78";
    let weight = 2.0;

    if (vuln >= 0.8) {
      color = "#A7473F";
      weight = 3.2;
    } else if (vuln >= 0.5) {
      color = "#C47B5A";
      weight = 2.6;
    }

    if (isSelected) {
      return {
        color: "#2B4441",
        weight: weight + 2.5,
        opacity: 1.0
      };
    }

    return {
      color: color,
      weight: weight,
      opacity: 0.82
    };
  };

  return (
    <div
      className={`relative rounded-xl overflow-hidden border border-[#DDD4C5] bg-[#E2DBD0] transition-all duration-300 ${
        isFullscreen ? "fixed inset-0 z-[2000] rounded-none border-none h-screen w-screen" : ""
      }`}
      style={{ height: isFullscreen ? "100vh" : height }}
    >
      <MapContainer
        center={[19.065, 72.875]} // Centered on Kurla / BKC Corridor
        zoom={13}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={false}
      >
        <MapResizeHandler isFullscreen={isFullscreen} />
        <ScaleControl position="bottomleft" imperial={false} />

        {/* 1. Official Basemap Layer */}
        {basemap === "google_streets" && (
          <TileLayer
            attribution="Map data &copy; Google Maps"
            url={`https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}${googleApiKey ? `&key=${googleApiKey}` : ""}`}
            subdomains={["0", "1", "2", "3"]}
            maxZoom={20}
          />
        )}

        {basemap === "google_satellite" && (
          <TileLayer
            attribution="Imagery &copy; Google Maps"
            url={`https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}${googleApiKey ? `&key=${googleApiKey}` : ""}`}
            subdomains={["0", "1", "2", "3"]}
            maxZoom={20}
          />
        )}

        {basemap === "google_terrain" && (
          <TileLayer
            attribution="Terrain &copy; Google Maps"
            url={`https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}${googleApiKey ? `&key=${googleApiKey}` : ""}`}
            subdomains={["0", "1", "2", "3"]}
            maxZoom={20}
          />
        )}

        {basemap === "osm" && (
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={18}
          />
        )}

        {/* 2. Administrative Wards Layer */}
        {layers.wards && wardsGeoJSON && (
          <GeoJSON
            key={JSON.stringify(wardsGeoJSON)}
            data={wardsGeoJSON}
            style={wardStyle}
            onEachFeature={(feature, layer) => {
              const p = feature.properties;
              layer.bindPopup(`
                <div style="font-size: 11.5px; line-height: 1.4;">
                  <strong style="color: #343D38; font-size: 12.5px;">${p.name || "Mumbai Ward"}</strong>
                  <div style="margin-top: 4px; color: #817B70;">
                    <div>Population: <b>${p.population?.toLocaleString() || "N/A"}</b></div>
                    <div>Area: <b>${p.area_sq_km || p.area_km2 || "N/A"} km²</b></div>
                    <div>Mean Elevation: <b>${p.elevation_mean_m || "N/A"} m MSL</b></div>
                  </div>
                </div>
              `);
            }}
          />
        )}

        {/* 3. Waterways & Canals */}
        {layers.waterways && waterwaysGeoJSON && (
          <GeoJSON
            key="waterways-layer"
            data={waterwaysGeoJSON}
            style={{
              color: "#3A7CA5",
              weight: 3.5,
              opacity: 0.9
            }}
            onEachFeature={(feature, layer) => {
              layer.on({
                click: () => {
                  if (onSelectFeature) {
                    onSelectFeature({
                      id: feature.properties?.id || "WATERWAY",
                      name: feature.properties?.name || "Mithi River Canal",
                      type: "waterway",
                      properties: feature.properties
                    });
                  }
                }
              });
            }}
          />
        )}

        {/* 4. Active Scenario Risk Zones */}
        {layers.riskZones && riskMapGeoJSON && (
          <GeoJSON
            key={JSON.stringify(riskMapGeoJSON)}
            data={riskMapGeoJSON}
            style={riskStyle}
          />
        )}

        {/* 5. Road Network Segments (OSM Real Data) */}
        {layers.roads && roadsGeoJSON && (
          <GeoJSON
            key={`roads-layer-${roadsGeoJSON?.features?.length || 0}`}
            data={roadsGeoJSON}
            style={roadStyle}
            onEachFeature={(feature, layer) => {
              layer.on({
                click: () => {
                  if (onSelectFeature) {
                    onSelectFeature({
                      id: feature.properties?.id || "OSM_ROAD",
                      name: feature.properties?.name || "Road Corridor",
                      type: "road",
                      properties: feature.properties
                    });
                  }
                }
              });
            }}
          />
        )}

        {/* 6. Critical Facilities Markers */}
        {layers.facilities && infraGeoJSON?.features?.map((feat: any, idx: number) => {
          const coords = feat.geometry?.coordinates;
          if (!coords || coords.length < 2) return null;
          const p = feat.properties;
          let icon = hospitalIcon;
          if (p.feature_type === "school") icon = schoolIcon;
          if (p.feature_type === "fire_station") icon = fireIcon;

          return (
            <Marker
              key={`infra-${idx}`}
              position={[coords[1], coords[0]]}
              icon={icon}
              eventHandlers={{
                click: () => {
                  if (onSelectFeature) {
                    onSelectFeature({
                      id: p.id || `FACILITY_${idx}`,
                      name: p.name || "Critical Facility",
                      type: "facility",
                      properties: p
                    });
                  }
                }
              }}
            />
          );
        })}

        {/* 7. Active Route Polyline */}
        {activeRoute?.route_geometry?.coordinates && (
          <Polyline
            positions={activeRoute.route_geometry.coordinates.map((c: any) => [c[1], c[0]])}
            pathOptions={{
              color: activeRoute.status === "DETOUR_REQUIRED" ? "#C47B5A" : "#527C78",
              weight: 4.5,
              opacity: 0.95
            }}
          />
        )}
      </MapContainer>

      {/* Top Map Action Bar: Basemap Switcher & Fullscreen */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5 bg-[#FFFCF6]/95 backdrop-blur-sm border border-[#DDD4C5] p-1 rounded-lg shadow-sm text-xs">
        {/* Basemap Selector */}
        <div className="flex items-center gap-1 pr-1 border-r border-[#DDD4C5]">
          <button
            onClick={() => setBasemap("google_streets")}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              basemap === "google_streets" ? "bg-[#527C78] text-white" : "text-[#817B70] hover:text-[#343D38]"
            }`}
            title="Google Maps Roadmap (Streets)"
          >
            Google Streets
          </button>
          <button
            onClick={() => setBasemap("google_satellite")}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              basemap === "google_satellite" ? "bg-[#527C78] text-white" : "text-[#817B70] hover:text-[#343D38]"
            }`}
            title="Google Maps Satellite Hybrid"
          >
            Satellite
          </button>
          <button
            onClick={() => setBasemap("google_terrain")}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              basemap === "google_terrain" ? "bg-[#527C78] text-white" : "text-[#817B70] hover:text-[#343D38]"
            }`}
            title="Google Maps Topographic Terrain"
          >
            Terrain
          </button>
          <button
            onClick={() => setBasemap("osm")}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              basemap === "osm" ? "bg-[#527C78] text-white" : "text-[#817B70] hover:text-[#343D38]"
            }`}
            title="OpenStreetMap Standard"
          >
            OSM
          </button>
        </div>

        {/* Fullscreen Toggle */}
        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          className="p-1 text-[#817B70] hover:text-[#343D38] rounded hover:bg-[#EEE7DA] transition-colors"
          title={isFullscreen ? "Exit Fullscreen" : "Fullscreen GIS View"}
        >
          {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Floating Layer Controls Panel */}
      <div className="absolute top-3 left-3 z-[1000] bg-[#FFFCF6]/95 backdrop-blur-sm border border-[#DDD4C5] rounded-xl p-3 shadow-sm max-w-xs text-xs">
        <div className="flex items-center justify-between font-semibold text-[#343D38] pb-2 border-b border-[#DDD4C5] mb-2">
          <span className="flex items-center gap-1.5 text-xs">
            <Layers className="w-3.5 h-3.5 text-[#527C78]" />
            GIS Layer Registry
          </span>
          <button
            onClick={() => setShowLayerPanel(!showLayerPanel)}
            className="text-[#817B70] hover:text-[#343D38]"
          >
            {showLayerPanel ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
          </button>
        </div>

        {showLayerPanel && (
          <div className="space-y-1.5 text-[11px]">
            <label className="flex items-center justify-between cursor-pointer text-[#343D38] hover:bg-[#EEE7DA]/50 px-1 py-0.5 rounded">
              <span className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={layers.riskZones}
                  onChange={() => toggleLayer("riskZones")}
                  className="rounded accent-[#C47B5A]"
                />
                <span>Flood Hazard Zones</span>
              </span>
              <span className="badge-predicted text-[9px] py-0 px-1">Predicted</span>
            </label>

            <label className="flex items-center justify-between cursor-pointer text-[#343D38] hover:bg-[#EEE7DA]/50 px-1 py-0.5 rounded">
              <span className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={layers.roads}
                  onChange={() => toggleLayer("roads")}
                  className="rounded accent-[#527C78]"
                />
                <span>Road Network (6,768)</span>
              </span>
              <span className="badge-observed text-[9px] py-0 px-1">Real Data</span>
            </label>

            <label className="flex items-center justify-between cursor-pointer text-[#343D38] hover:bg-[#EEE7DA]/50 px-1 py-0.5 rounded">
              <span className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={layers.facilities}
                  onChange={() => toggleLayer("facilities")}
                  className="rounded accent-[#A7473F]"
                />
                <span>Hospitals &amp; Schools (22)</span>
              </span>
              <span className="badge-observed text-[9px] py-0 px-1">Observed</span>
            </label>

            <label className="flex items-center justify-between cursor-pointer text-[#343D38] hover:bg-[#EEE7DA]/50 px-1 py-0.5 rounded">
              <span className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={layers.waterways}
                  onChange={() => toggleLayer("waterways")}
                  className="rounded accent-[#3A7CA5]"
                />
                <span>Mithi River Channels</span>
              </span>
              <span className="badge-observed text-[9px] py-0 px-1">Observed</span>
            </label>

            <label className="flex items-center justify-between cursor-pointer text-[#343D38] hover:bg-[#EEE7DA]/50 px-1 py-0.5 rounded">
              <span className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={layers.wards}
                  onChange={() => toggleLayer("wards")}
                  className="rounded accent-[#A3B18A]"
                />
                <span>Administrative Wards</span>
              </span>
              <span className="text-[9px] text-[#817B70]">Vector</span>
            </label>
          </div>
        )}
      </div>

      {/* Floating Scientific Legend */}
      <div className="absolute bottom-3 left-16 z-[1000] bg-[#FFFCF6]/95 backdrop-blur-sm border border-[#DDD4C5] rounded-xl p-2.5 shadow-sm text-xs max-w-xs hidden sm:block">
        <div className="flex items-center gap-1 font-semibold text-[#343D38] text-[11px] mb-1.5">
          <Info className="w-3 h-3 text-[#527C78]" />
          <span>Cartographic Legend</span>
        </div>
        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10.5px] text-[#817B70]">
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#A7473F]"></span>
            <span>Critical Susceptibility</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#C47B5A]"></span>
            <span>High Risk Corridor</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-1 bg-[#3A7CA5]"></span>
            <span>Discharge Canal</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-[#A7473F] border border-white"></span>
            <span>Emergency Hospital</span>
          </div>
        </div>
      </div>

      {/* Mandatory Attribution Footer Bar */}
      <div className="absolute bottom-2 right-2 z-[1000] bg-[#FFFCF6]/90 backdrop-blur-sm border border-[#DDD4C5] rounded px-2 py-0.5 text-[10px] text-[#817B70] shadow-2xs">
        Map data &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline hover:text-[#527C78]">OpenStreetMap</a> contributors &bull; Basemaps &copy; Google Maps Platform
      </div>
    </div>
  );
};
