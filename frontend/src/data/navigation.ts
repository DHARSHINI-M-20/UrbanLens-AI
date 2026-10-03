import {
  BarChart3,
  Building2,
  FileSearch,
  ListChecks,
  LayoutDashboard,
  Map,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string;
}

export const NAV_MAIN: NavItem[] = [
  { id: "overview", label: "Dashboard", icon: LayoutDashboard, path: "/" },
  { id: "map", label: "Map Intelligence", icon: Map, path: "/map" },
  { id: "properties", label: "Properties", icon: Building2, path: "/properties" },
  { id: "analytics", label: "Analytics", icon: BarChart3, path: "/analytics" },
  { id: "history", label: "Analysis History", icon: FileSearch, path: "/history" },
  { id: "queries", label: "Task 5 Queries", icon: ListChecks, path: "/challenge-queries" },
];

export const NAV_MANAGEMENT: NavItem[] = [
  { id: "review", label: "Review Queue", icon: ShieldCheck, path: "/review" },
  { id: "settings", label: "Settings", icon: Settings, path: "/settings" },
];
