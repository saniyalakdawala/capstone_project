import React, { useState } from "react";
import {
  Globe2,
  MapPin,
  CloudRain,
  Activity,
  Layers,
  ShieldAlert,
  Database,
  BarChart3,
  Calendar,
  Menu,
  X,
  Clock,
  CheckCircle2
} from "lucide-react";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedWard: string;
  setSelectedWard: (ward: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  selectedWard,
  setSelectedWard
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const tabs = [
    { id: "overview", label: "Overview", icon: Activity },
    { id: "map", label: "Live Map", icon: Layers },
    { id: "simulator", label: "Scenario Simulator", icon: CloudRain },
    { id: "infrastructure", label: "Infrastructure", icon: ShieldAlert },
    { id: "population", label: "Population Exposure", icon: MapPin },
    { id: "history", label: "Historical Events", icon: Calendar },
    { id: "research", label: "Research Insights", icon: BarChart3 },
    { id: "pipeline", label: "Data Pipeline", icon: Database }
  ];

  return (
    <header className="bg-[#FFFCF6] border-b border-[#DDD4C5] sticky top-0 z-50 shadow-2xs backdrop-blur-md">
      {/* Primary Top Header Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 border-b border-[#DDD4C5]/60 gap-4">
          {/* Product Identity */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#527C78] flex items-center justify-center text-white shadow-2xs">
              <Globe2 className="w-4 h-4 text-[#EEE7DA]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="serif-heading text-lg font-bold text-[#343D38] tracking-tight">
                  Earth Intelligence
                </span>
                <span className="text-[10px] uppercase font-bold text-[#527C78] tracking-widest bg-[#527C78]/10 px-1.5 py-0.5 rounded border border-[#527C78]/25">
                  Digital Twin
                </span>
              </div>
              <p className="text-[11px] text-[#817B70] hidden sm:block">
                Mumbai Metropolitan Region &bull; Regional Flood Intelligence
              </p>
            </div>
          </div>

          {/* Center/Right Status & Study Area Selector */}
          <div className="flex items-center gap-2.5">
            {/* Study Area Selector */}
            <div className="flex items-center gap-1.5 bg-[#EEE7DA]/70 px-2.5 py-1 rounded-md border border-[#DDD4C5] text-xs">
              <span className="text-[#817B70] font-medium hidden md:inline">Study Area:</span>
              <select
                value={selectedWard}
                onChange={(e) => setSelectedWard(e.target.value)}
                className="bg-transparent text-xs font-semibold text-[#343D38] focus:outline-none cursor-pointer"
              >
                <option value="MUM_WARD_L_KURLA">Ward L (Kurla - Mithi River)</option>
                <option value="MUM_WARD_FN_SION">Ward F/North (Sion - Matunga)</option>
                <option value="MUM_WARD_HE_BANDRA_E">Ward H/East (Bandra East - BKC)</option>
                <option value="MUM_WARD_GN_DHARAVI">Ward G/North (Dharavi - Mahim)</option>
                <option value="MUM_WARD_KW_ANDHERI_W">Ward K/West (Andheri - Juhu)</option>
                <option value="MUMBAI_ALL">Greater Mumbai Extent</option>
              </select>
            </div>

            {/* Scientific Data Freshness vs Application Status (Section 4 Requirement) */}
            <div className="hidden lg:flex items-center gap-3 text-[11px] border-l border-[#DDD4C5] pl-3 text-[#817B70]">
              <div className="flex items-center gap-1" title="Dataset observation freshness">
                <Clock className="w-3.5 h-3.5 text-[#527C78]" />
                <span>OSM Ingested: <b className="text-[#343D38]">6,768 segs</b></span>
              </div>
              <div className="flex items-center gap-1.5" title="Backend service status">
                <span className="w-2 h-2 rounded-full bg-[#527C78] animate-pulse"></span>
                <span>System: <b className="text-[#527C78]">Online</b></span>
              </div>
            </div>

            {/* Mobile Menu Hamburger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 text-[#817B70] hover:text-[#343D38] rounded-md hover:bg-[#EEE7DA]"
              aria-label="Toggle navigation"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Desktop Navigation Tabs */}
        <nav className="hidden md:flex space-x-1 py-1.5 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-[#527C78] text-white shadow-2xs font-semibold"
                    : "text-[#817B70] hover:text-[#343D38] hover:bg-[#EEE7DA]"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-white" : "text-[#527C78]"}`} />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#FFFCF6] border-b border-[#DDD4C5] px-4 py-3 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-[#527C78] text-white font-semibold"
                    : "text-[#817B70] hover:text-[#343D38] hover:bg-[#EEE7DA]"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-white" : "text-[#527C78]"}`} />
                {tab.label}
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
};
