import InteractiveMap from "../components/InteractiveMap";
import FilterBar from "../components/FilterBar";
import SearchBar from "../components/SearchBar";
import { useDashboard } from "../context/DashboardContext";

export default function MapIntelligence() {
  const {
    filteredBuildings,
    selectBuilding,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    buildingTypeFilter,
    setBuildingTypeFilter,
    confidenceFilter,
    setConfidenceFilter,
    streets,
    studyArea,
    studyAreaMetadata,
    samplingPoints,
    selectedStreet,
    setSelectedStreet,
  } = useDashboard();

  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">GEOSPATIAL INTELLIGENCE</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Map Intelligence</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">
          {String((studyAreaMetadata?.properties as Record<string, unknown> | undefined)?.townname ?? "Official study area")} · {streets.length} imported simulated streets · {samplingPoints.length} coverage samples
        </p>
      </div>

      <div className="mb-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[2fr_1fr_1fr]">
          <SearchBar value={search} onChange={setSearch} />
          <label className="flex items-center gap-2 text-xs text-slate-400">
            Street
            <select value={selectedStreet} onChange={(event) => setSelectedStreet(event.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-white/10 bg-[#11162d] px-3 py-2 text-xs text-slate-200">
              <option value="All">All streets</option>
              {streets.map((street) => <option key={String(street.street_id)} value={String(street.street_id)}>{String(street.name)}</option>)}
            </select>
          </label>
          <div className="flex items-center justify-end text-xs text-slate-500">
            {filteredBuildings.length} observations match current filters
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

      <InteractiveMap buildings={filteredBuildings} streets={selectedStreet === "All" ? streets : streets.filter((street) => street.street_id === selectedStreet)} samplingPoints={samplingPoints} studyArea={studyArea} onBuildingSelect={selectBuilding} />
    </div>
  );
}
