import React from "react";
import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  badge?: string;
  badgeType?: "critical" | "high" | "normal" | "neutral";
  dataType?: "observed" | "predicted" | "simulated" | "estimated";
  timeReference?: string;
  source?: string;
  icon?: LucideIcon;
  iconColor?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  subtitle,
  badge,
  badgeType = "normal",
  dataType = "observed",
  timeReference,
  source,
  icon: Icon,
  iconColor = "text-[#527C78]"
}) => {
  const getBadgeClass = () => {
    switch (badgeType) {
      case "critical":
        return "badge-critical";
      case "high":
        return "badge-predicted";
      case "normal":
        return "badge-observed";
      default:
        return "bg-[#EEE7DA] text-[#343D38] text-[10px] px-1.5 py-0.5 rounded";
    }
  };

  const getDataTypeBadge = () => {
    switch (dataType) {
      case "observed":
        return "badge-observed";
      case "predicted":
        return "badge-predicted";
      case "simulated":
        return "badge-simulated";
      case "estimated":
        return "bg-[#A3B18A]/20 text-[#4E6847] border border-[#A3B18A]/40 text-[9px] px-1 rounded uppercase font-semibold";
      default:
        return "badge-observed";
    }
  };

  return (
    <div className="gis-surface p-4 flex flex-col justify-between hover:border-[#C8BFB0] transition-colors">
      <div>
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className={`${getDataTypeBadge()} text-[9px] py-0 px-1`}>
              {dataType}
            </span>
            {timeReference && (
              <span className="text-[10px] text-[#817B70]">{timeReference}</span>
            )}
          </div>
          {Icon && (
            <div className="w-7 h-7 rounded-md bg-[#EEE7DA]/60 flex items-center justify-center border border-[#DDD4C5]/60 shrink-0">
              <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
            </div>
          )}
        </div>

        <p className="text-xs font-medium text-[#817B70] leading-snug">{title}</p>
        
        <div className="flex items-baseline gap-1 mt-1">
          <h3 className="serif-heading text-2xl font-bold text-[#343D38] tracking-tight">
            {value}
          </h3>
          {unit && <span className="text-xs text-[#817B70] font-medium">{unit}</span>}
        </div>
      </div>

      <div className="mt-2.5 pt-2 border-t border-[#DDD4C5]/50 flex items-center justify-between text-[11px]">
        <div className="truncate max-w-[170px]" title={source || subtitle}>
          <span className="text-[#817B70] text-[10px] block truncate">
            {source ? `Src: ${source}` : subtitle}
          </span>
        </div>
        {badge && <span className={`${getBadgeClass()} text-[9.5px]`}>{badge}</span>}
      </div>
    </div>
  );
};
