import React, { useState } from "react";
import { Navbar } from "./components/Navbar";
import { Overview } from "./pages/Overview";
import { LiveMapPage } from "./pages/LiveMapPage";
import { ScenarioSimulator } from "./pages/ScenarioSimulator";
import { InfrastructureImpact } from "./pages/InfrastructureImpact";
import { PopulationExposure } from "./pages/PopulationExposure";
import { HistoricalEvents } from "./pages/HistoricalEvents";
import { ResearchInsights } from "./pages/ResearchInsights";
import { DataPipelinePanel } from "./pages/DataPipelinePanel";

export function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedWard, setSelectedWard] = useState("MUM_WARD_L_KURLA");

  return (
    <div className="min-h-screen bg-[#F5F0E6] flex flex-col">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedWard={selectedWard}
        setSelectedWard={setSelectedWard}
      />

      {/* Main Workspace Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === "overview" && (
          <Overview selectedWard={selectedWard} setActiveTab={setActiveTab} />
        )}
        {activeTab === "map" && (
          <LiveMapPage selectedWard={selectedWard} setSelectedWard={setSelectedWard} />
        )}
        {activeTab === "simulator" && (
          <ScenarioSimulator selectedWard={selectedWard} />
        )}
        {activeTab === "infrastructure" && (
          <InfrastructureImpact />
        )}
        {activeTab === "population" && (
          <PopulationExposure />
        )}
        {activeTab === "history" && (
          <HistoricalEvents />
        )}
        {activeTab === "research" && (
          <ResearchInsights />
        )}
        {activeTab === "pipeline" && (
          <DataPipelinePanel />
        )}
      </main>

      {/* Research Disclaimer & Scientific Footer */}
      <footer className="bg-[#FFFCF6] border-t border-[#DDD4C5] py-5 text-xs text-[#817B70] mt-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-3">
          <div>
            <span className="font-semibold text-[#343D38]">
              Earth Intelligence Digital Twin (EIDT) — Mumbai Flood Modeling Prototype
            </span>
            <p className="mt-0.5 text-[11px]">
              Geospatial disaster scenario research platform. Susceptibility scores reflect hydrodynamic modeling and do not constitute an official municipal emergency broadcast.
            </p>
          </div>
          <div className="flex items-center gap-3 text-[11px] whitespace-nowrap text-[#817B70]">
            <span>CRS: <b className="text-[#343D38]">EPSG:4326</b> / UTM 43N</span>
            <span>&bull;</span>
            <span>Database: <b className="text-[#527C78]">PostgreSQL &amp; PostGIS</b></span>
            <span>&bull;</span>
            <span>Platform v1.4.2</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
