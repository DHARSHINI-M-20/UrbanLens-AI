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

export default function KPICards() {
  const cards = [
    { title: "Streets Analysed", value: "1,250", icon: Map, description: "Street segments processed", accent: "#38bdf8" },
    { title: "Buildings Detected", value: "1,248", icon: Building2, description: "AI detected buildings", accent: "#818cf8" },
    { title: "Buildings Matched", value: "986", icon: CheckCircle2, description: "Successfully matched", accent: "#34d399" },
    { title: "Unmatched Properties", value: "142", icon: AlertTriangle, description: "Require verification", accent: "#f87171" },
    { title: "Streetlights", value: "436", icon: Lightbulb, description: "Streetlights detected", accent: "#fbbf24" },
    { title: "Electric Poles", value: "318", icon: Zap, description: "Utility poles detected", accent: "#c084fc" },
    { title: "Low Confidence", value: "76", icon: Activity, description: "AI confidence below threshold", accent: "#fb923c" },
    { title: "Review Items", value: "54", icon: Search, description: "Pending human review", accent: "#22d3ee" },
  ];

  return (
    <section className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <KPICard key={card.title} {...card} />
      ))}
    </section>
  );
}
