import React, { useState, useEffect } from "react";
import {
  CloudRain,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Info,
  Sliders,
  TrendingUp,
  ShieldCheck
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";
import { createScenario, fetchExposureAnalytics } from "../services/api";

interface ScenarioSimulatorProps {
  selectedWard: string;
}

export const ScenarioSimulator: React.FC<ScenarioSimulatorProps> = ({ selectedWard }) => {
  // Scenario Configuration State
  const [rainfallMm, setRainfallMm] = useState(200);
  const [durationHours, setDurationHours] = useState(24);
  const [soilSaturation, setSoilSaturation] = useState(80);
  const [drainageEfficiency, setDrainageEfficiency] = useState(75);
  const [tideHeight, setTideHeight] = useState(4.2);
  const [desilting, setDesilting] = useState(false);
  const [extraPumps, setExtraPumps] = useState(false);
  const [scenarioName, setScenarioName] = useState("Custom Monsoon Simulation");

  // Running & Results State
  const [isSimulating, setIsSimulating] = useState(false);
  const [activeResult, setActiveResult] = useState<any>(null);
  const [exposureData, setExposureData] = useState<any>(null);

  useEffect(() => {
    // Initial fetch of default comparisons
    fetchExposureAnalytics("SCEN_HEAVY_200MM").then((data) => {
      setExposureData(data);
    });
  }, []);

  // Quick Preset Selection
  const applyPreset = (name: string, rain: number, dur: number, desilt: boolean) => {
    setScenarioName(name);
    setRainfallMm(rain);
    setDurationHours(dur);
    setDesilting(desilt);
  };

  const handleRunSimulation = async () => {
    setIsSimulating(true);
    try {
      const payload = {
        study_area_id: selectedWard || "MUM_WARD_L_KURLA",
        scenario_name: scenarioName,
        rainfall_total_mm: Number(rainfallMm),
        duration_hours: Number(durationHours),
        assumptions: {
          soil_saturation_pct: Number(soilSaturation),
          drainage_efficiency_pct: Number(drainageEfficiency),
          high_tide_height_m: Number(tideHeight)
        },
        mitigation_features: {
          mithi_river_desilting: desilting,
          additional_pumping_stations: extraPumps,
          holding_ponds_active: false
        }
      };

      const resp = await createScenario(payload);
      setActiveResult(resp.simulation_result);

      // Refresh exposure analytics comparisons
      const expRes = await fetchExposureAnalytics(resp.scenario.scenario_id);
      setExposureData(expRes);
    } catch (err) {
      console.error("Simulation error:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  const metrics = activeResult?.summary_metrics || exposureData?.summary || {
    rainfall_total_mm: 200,
    high_risk_area_sqkm: 21.6,
    estimated_exposed_population: 386000,
    exposed_hospitals_count: 3,
    affected_road_segments_count: 6,
    affected_road_length_km: 28.5,
    accessibility_reduction_pct: 56.0
  };

  const uncertainty = activeResult?.uncertainty_metadata || {
    confidence_interval_95_sqkm: [18.5, 25.1],
    epistemic_uncertainty_index: 0.18,
    effective_runoff_mm: 168.0,
    mitigation_benefit_pct: desilting || extraPumps ? 24.5 : 0.0
  };

  return (
    <div className="space-y-6">
      {/* Title & Introduction */}
      <div className="bg-[#FFFCF6] border border-[#DDD4C5] rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold uppercase tracking-wider text-[#527C78]">
            Hydrological Engine &amp; SCS-CN Modeling
          </span>
          <span className="badge-normal text-[10px]">Deterministic + Random Forest Synthesis</span>
        </div>
        <h1 className="serif-heading text-3xl font-bold text-[#343D38]">
          Flood Scenario Simulator
        </h1>
        <p className="text-sm text-[#817B70] mt-1 max-w-3xl">
          Investigate non-linear urban flood consequences under hypothetical precipitation totals, tidal lock conditions, and mitigation interventions. Every run computes runoff depth, infrastructure severing, and population exposure.
        </p>

        {/* Quick Presets */}
        <div className="mt-4 pt-4 border-t border-[#DDD4C5]/60 flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-[#817B70]">Demonstration Presets:</span>
          <button
            onClick={() => applyPreset("Moderate Rainfall (100mm / 24h)", 100, 24, false)}
            className="px-3 py-1 bg-[#F5F0E6] hover:bg-[#EEE7DA] text-[#343D38] border border-[#DDD4C5] rounded-lg text-xs font-medium"
          >
            Moderate (100 mm)
          </button>
          <button
            onClick={() => applyPreset("Heavy Monsoon (200mm / 24h)", 200, 24, false)}
            className="px-3 py-1 bg-[#F5F0E6] hover:bg-[#EEE7DA] text-[#343D38] border border-[#DDD4C5] rounded-lg text-xs font-medium"
          >
            Heavy (200 mm)
          </button>
          <button
            onClick={() => applyPreset("Extreme Deluge (300mm / 24h)", 300, 24, false)}
            className="px-3 py-1 bg-[#F5F0E6] hover:bg-[#EEE7DA] text-[#343D38] border border-[#DDD4C5] rounded-lg text-xs font-medium"
          >
            Extreme (300 mm)
          </button>
          <button
            onClick={() => applyPreset("Mitigated Extreme Event", 300, 24, true)}
            className="px-3 py-1 bg-[#A3B18A]/20 hover:bg-[#A3B18A]/40 text-[#527C78] border border-[#A3B18A]/40 rounded-lg text-xs font-medium"
          >
            300 mm + Mithi Dredging Active
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Interactive Simulation Controls */}
        <div className="gis-surface space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#DDD4C5]">
            <h3 className="serif-heading text-lg font-bold text-[#343D38] flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-[#527C78]" />
              Scenario Parameters
            </h3>
            <span className="text-xs text-[#817B70] font-medium">Input Controls</span>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#343D38] flex justify-between">
              <span>Rainfall Accumulation</span>
              <span className="font-bold text-[#A7473F]">{rainfallMm} mm</span>
            </label>
            <input
              type="range"
              min="50"
              max="500"
              step="10"
              value={rainfallMm}
              onChange={(e) => setRainfallMm(Number(e.target.value))}
              className="w-full accent-[#527C78] mt-1.5"
            />
            <div className="flex justify-between text-[10px] text-[#817B70]">
              <span>50 mm (Advisory)</span>
              <span>250 mm (Severe)</span>
              <span>500 mm (Catastrophic)</span>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#343D38] flex justify-between">
              <span>Rainfall Duration</span>
              <span className="font-bold text-[#343D38]">{durationHours} Hours</span>
            </label>
            <input
              type="range"
              min="3"
              max="48"
              step="3"
              value={durationHours}
              onChange={(e) => setDurationHours(Number(e.target.value))}
              className="w-full accent-[#527C78] mt-1.5"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#343D38] flex justify-between">
              <span>Antecedent Soil Saturation</span>
              <span className="font-bold text-[#343D38]">{soilSaturation}%</span>
            </label>
            <input
              type="range"
              min="40"
              max="100"
              step="5"
              value={soilSaturation}
              onChange={(e) => setSoilSaturation(Number(e.target.value))}
              className="w-full accent-[#527C78] mt-1.5"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#343D38] flex justify-between">
              <span>Arabian Sea Astronomical High Tide</span>
              <span className="font-bold text-[#C47B5A]">{tideHeight} m</span>
            </label>
            <input
              type="range"
              min="2.5"
              max="5.2"
              step="0.1"
              value={tideHeight}
              onChange={(e) => setTideHeight(Number(e.target.value))}
              className="w-full accent-[#527C78] mt-1.5"
            />
          </div>

          {/* Mitigation Interventions */}
          <div className="pt-3 border-t border-[#DDD4C5] space-y-2">
            <span className="text-xs font-bold text-[#343D38] uppercase tracking-wider">
              Mitigation Measures
            </span>
            <label className="flex items-center gap-2 cursor-pointer text-xs text-[#343D38]">
              <input
                type="checkbox"
                checked={desilting}
                onChange={(e) => setDesilting(e.target.checked)}
                className="rounded accent-[#527C78]"
              />
              <span>Mithi River Desilting &amp; Dredging (-16% peak)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-xs text-[#343D38]">
              <input
                type="checkbox"
                checked={extraPumps}
                onChange={(e) => setExtraPumps(e.target.checked)}
                className="rounded accent-[#527C78]"
              />
              <span>Pumping Stations at Full Capacity (-10%)</span>
            </label>
          </div>

          {/* Execute Button */}
          <button
            onClick={handleRunSimulation}
            disabled={isSimulating}
            className="w-full btn-primary justify-center py-2.5 mt-2"
          >
            {isSimulating ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                Executing SCS-CN Engine...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Play className="w-4 h-4 fill-current" />
                Run Simulation Engine
              </span>
            )}
          </button>
        </div>

        {/* Right 2 Columns: Computed Results & Comparisons */}
        <div className="lg:col-span-2 space-y-6">
          {/* Simulation Output Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-[#FFFCF6] border border-[#DDD4C5] rounded-xl">
              <span className="text-[10px] font-bold text-[#817B70] uppercase">High Risk Area</span>
              <div className="serif-heading text-xl font-bold text-[#A7473F] mt-1">
                {metrics.high_risk_area_sqkm} km²
              </div>
              <span className="text-[10px] text-[#817B70]">
                95% CI: [{uncertainty.confidence_interval_95_sqkm?.[0]}, {uncertainty.confidence_interval_95_sqkm?.[1]}]
              </span>
            </div>

            <div className="p-3 bg-[#FFFCF6] border border-[#DDD4C5] rounded-xl">
              <span className="text-[10px] font-bold text-[#817B70] uppercase">Exposed Pop.</span>
              <div className="serif-heading text-xl font-bold text-[#343D38] mt-1">
                {metrics.estimated_exposed_population?.toLocaleString()}
              </div>
              <span className="text-[10px] text-[#817B70]">WorldPop 100m grid</span>
            </div>

            <div className="p-3 bg-[#FFFCF6] border border-[#DDD4C5] rounded-xl">
              <span className="text-[10px] font-bold text-[#817B70] uppercase">Hospitals Severed</span>
              <div className="serif-heading text-xl font-bold text-[#C47B5A] mt-1">
                {metrics.exposed_hospitals_count}
              </div>
              <span className="text-[10px] text-[#817B70]">Direct flood cut-off</span>
            </div>

            <div className="p-3 bg-[#FFFCF6] border border-[#DDD4C5] rounded-xl">
              <span className="text-[10px] font-bold text-[#817B70] uppercase">Road Reduction</span>
              <div className="serif-heading text-xl font-bold text-[#527C78] mt-1">
                -{metrics.accessibility_reduction_pct}%
              </div>
              <span className="text-[10px] text-[#817B70]">{metrics.affected_road_length_km} km flooded</span>
            </div>
          </div>

          {/* Scenario Comparison Chart */}
          <div className="gis-surface">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="serif-heading text-lg font-bold text-[#343D38]">
                  Multi-Scenario Impact Progression
                </h3>
                <p className="text-xs text-[#817B70]">
                  Comparing rainfall accumulation against flooded area (km²) and exposed population (in 10k)
                </p>
              </div>
              <span className="badge-normal text-[10px]">Model Run MR_EIDT_RF_V1</span>
            </div>

            <div className="h-60 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={(exposureData?.scenario_comparisons || []).map((sc: any) => ({
                    name: `${sc.rainfall_mm}mm`,
                    "Flooded Area (km²)": sc.high_risk_area_sqkm,
                    "Exposed Pop (x10k)": Math.round(sc.exposed_population / 10000),
                    "Affected Corridors": sc.affected_roads_count
                  }))}
                  margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
                >
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#817B70" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#817B70" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#FFFCF6",
                      border: "1px solid #DDD4C5",
                      borderRadius: "8px",
                      fontSize: "12px"
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
                  <Bar dataKey="Flooded Area (km²)" fill="#C47B5A" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Exposed Pop (x10k)" fill="#527C78" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Affected Corridors" fill="#A3B18A" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Uncertainty & Scientific Limitations */}
          <div className="bg-[#FFFCF6] border border-[#DDD4C5] rounded-xl p-4 text-xs text-[#817B70] space-y-2">
            <div className="font-semibold text-[#343D38] flex items-center gap-1.5">
              <Info className="w-4 h-4 text-[#527C78]" />
              Model Uncertainty &amp; Research Boundary Conditions
            </div>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <b>Epistemic Uncertainty Index:</b> {uncertainty.epistemic_uncertainty_index || 0.18} (Moderate). Uncertainty widens above 300mm where backwater interaction exceeds channel cross-sections.
              </li>
              <li>
                <b>Hydrological Assumption:</b> SCS-CN method estimates overland volume; street-scale drainage curb capacity is approximated via empirical coefficient.
              </li>
              <li>
                <b>Research Prototype Notice:</b> Output is an analytical planning tool, not an official flood warning or calibrated 2D hydraulic flood forecast.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
