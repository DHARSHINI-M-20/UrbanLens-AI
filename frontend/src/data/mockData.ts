import {
  Map,
  Building2,
  CheckCircle,
  Home,
  Lightbulb,
  Zap,
  AlertTriangle,
  ClipboardCheck,
} from "lucide-react";

export const kpiData = [
  {
    title: "Streets Analysed",
    value: 128,
    icon: Map,
    description: "Street segments processed",
  },
  {
    title: "Buildings Detected",
    value: 2456,
    icon: Building2,
    description: "Buildings identified by AI",
  },
  {
    title: "Buildings Matched",
    value: 1987,
    icon: CheckCircle,
    description: "Successfully matched",
  },
  {
    title: "Unmatched Properties",
    value: 469,
    icon: Home,
    description: "Properties requiring attention",
  },
  {
    title: "Streetlights",
    value: 834,
    icon: Lightbulb,
    description: "Streetlights detected",
  },
  {
    title: "Electric Poles",
    value: 612,
    icon: Zap,
    description: "Electric poles detected",
  },
  {
    title: "Low Confidence",
    value: 143,
    icon: AlertTriangle,
    description: "Observations below threshold",
  },
  {
    title: "Review Items",
    value: 87,
    icon: ClipboardCheck,
    description: "Items waiting for review",
  },
];