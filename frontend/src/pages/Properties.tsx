import DiscrepancyTable from "../components/DiscrepancyTable";
import FilterBar from "../components/FilterBar";
import SearchBar from "../components/SearchBar";
import { useDashboard } from "../context/DashboardContext";

export default function Properties() {
  const {
    discrepancies,
    selectBuilding,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    buildingTypeFilter,
    setBuildingTypeFilter,
    confidenceFilter,
    setConfidenceFilter,
  } = useDashboard();

  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">DATA QUALITY</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Property Discrepancies</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">
          Simulated observations compared with the reference records supplied to this dataset. “Unmatched” means no match in those records, not that no official property record exists.
        </p>
      </div>

      <div className="mb-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[2fr_1fr]">
          <SearchBar value={search} onChange={setSearch} />
          <div className="flex items-center justify-end text-xs text-slate-500">
            {discrepancies.length} records need verification
          </div>
        </div>
        <div className="mt-3">
          <FilterBar
            status={statusFilter}
            buildingType={buildingTypeFilter}
            confidence={confidenceFilter}
            setStatus={setStatusFilter}
            setBuildingType={setBuildingTypeFilter}
            setConfidence={setConfidenceFilter}
          />
        </div>
      </div>

      <DiscrepancyTable buildings={discrepancies} onSelect={selectBuilding} />
    </div>
  );
}
