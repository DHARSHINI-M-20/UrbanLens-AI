import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { buildings as allBuildings } from "../data/mockData";
import type { Building } from "../types";

function confidenceBucket(value: number) {
  if (value >= 80) return "High";
  if (value >= 60) return "Medium";
  return "Low";
}

interface DashboardContextValue {
  buildings: Building[];
  filteredBuildings: Building[];
  discrepancies: Building[];

  search: string;
  setSearch: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  buildingTypeFilter: string;
  setBuildingTypeFilter: (v: string) => void;
  confidenceFilter: string;
  setConfidenceFilter: (v: string) => void;

  selectedBuilding: Building | null;
  isDrawerOpen: boolean;
  selectBuilding: (building: Building) => void;
  closeDrawer: () => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [buildingTypeFilter, setBuildingTypeFilter] = useState("All");
  const [confidenceFilter, setConfidenceFilter] = useState("All");
  const [selectedBuilding, setSelectedBuilding] = useState<Building | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const filteredBuildings = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allBuildings.filter((b) => {
      const matchesSearch =
        !q ||
        b.id.toLowerCase().includes(q) ||
        b.street.toLowerCase().includes(q) ||
        b.ocr.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "All" || b.status === statusFilter;
      const matchesType = buildingTypeFilter === "All" || b.type === buildingTypeFilter;
      const matchesConfidence = confidenceFilter === "All" || confidenceBucket(b.confidence) === confidenceFilter;
      return matchesSearch && matchesStatus && matchesType && matchesConfidence;
    });
  }, [search, statusFilter, buildingTypeFilter, confidenceFilter]);

  const discrepancies = useMemo(
    () => filteredBuildings.filter((b) => b.status !== "MATCHED"),
    [filteredBuildings]
  );

  const value: DashboardContextValue = {
    buildings: allBuildings,
    filteredBuildings,
    discrepancies,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    buildingTypeFilter,
    setBuildingTypeFilter,
    confidenceFilter,
    setConfidenceFilter,
    selectedBuilding,
    isDrawerOpen,
    selectBuilding: (building) => {
      setSelectedBuilding(building);
      setIsDrawerOpen(true);
    },
    closeDrawer: () => setIsDrawerOpen(false),
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used within DashboardProvider");
  return ctx;
}
