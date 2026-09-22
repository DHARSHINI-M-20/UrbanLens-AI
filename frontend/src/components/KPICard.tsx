import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  description: string;
}

export default function KPICard({
  title,
  value,
  icon: Icon,
  description,
}: KPICardProps) {
  return (
    <div className="kpi-card">
      <div className="kpi-top">
        <div className="kpi-icon">
          <Icon size={20} />
        </div>
      </div>

      <h3>{value.toLocaleString()}</h3>
      <p className="kpi-title">{title}</p>
      <span className="kpi-description">{description}</span>
    </div>
  );
}