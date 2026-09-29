import {
  Activity,
  AlertTriangle,
  Building2,
  CheckCircle2,
  Lightbulb,
  Map,
  Search,
  Zap,
} from "lucide-react";

import KPICard from "./KPICard";
import { useDashboard } from "../context/DashboardContext";

export default function KPICards() {
  const { summary } = useDashboard();
  const value = (key: string) => Number(summary?.[key] ?? 0).toLocaleString();
  const cards = [
    { title: "Streets Covered", value: value("streets_covered"), icon: Map, description: "Simulated street segments", accent: "#38bdf8" },
    { title: "Buildings Analysed", value: value("buildings_analysed"), icon: Building2, description: "Persisted observations", accent: "#818cf8" },
    { title: "Unmatched Properties", value: value("unmatched_properties"), icon: AlertTriangle, description: "Unmatched, possible, or mismatched", accent: "#f87171" },
    { title: "Streetlights", value: value("streetlights_detected"), icon: Lightbulb, description: "Fixture observations", accent: "#fbbf24" },
    { title: "Electric Poles", value: value("electric_poles_detected"), icon: Zap, description: "Fixture observations", accent: "#c084fc" },
    { title: "Low Confidence", value: value("low_confidence_observations"), icon: Activity, description: "Below the review threshold", accent: "#fb923c" },
    { title: "Discrepancies", value: value("discrepancy_count"), icon: CheckCircle2, description: "Persisted demo findings", accent: "#34d399" },
    { title: "Reviews Pending", value: value("reviews_pending"), icon: Search, description: "Awaiting reviewer decision", accent: "#22d3ee" },
  ];

  return (
    <section className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <KPICard key={card.title} {...card} />
      ))}
    </section>
  );
}
