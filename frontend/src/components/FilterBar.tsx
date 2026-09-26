interface FilterBarProps {
  status: string;
  buildingType: string;
  confidence: string;
  setStatus: (value: string) => void;
  setBuildingType: (value: string) => void;
  setConfidence: (value: string) => void;
}

const selectClass =
  "w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-slate-200 focus:border-cyan-400/40 focus:outline-none";

export default function FilterBar({
  status,
  buildingType,
  confidence,
  setStatus,
  setBuildingType,
  setConfidence,
}: FilterBarProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div>
        <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">Status</label>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectClass}>
          <option value="All">All Status</option>
          <option value="MATCHED">Matched</option>
          <option value="PARTIAL">Partial</option>
          <option value="UNMATCHED">Unmatched</option>
          <option value="LOW CONFIDENCE">Low Confidence</option>
          <option value="NOT VERIFIED">Not Verified</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">Building Type</label>
        <select value={buildingType} onChange={(e) => setBuildingType(e.target.value)} className={selectClass}>
          <option value="All">All Types</option>
          <option value="Residential">Residential</option>
          <option value="Commercial">Commercial</option>
          <option value="Mixed-use">Mixed-use</option>
          <option value="Institutional">Institutional</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">Confidence</label>
        <select value={confidence} onChange={(e) => setConfidence(e.target.value)} className={selectClass}>
          <option value="All">All Levels</option>
          <option value="High">High 80%+</option>
          <option value="Medium">Medium 60–79%</option>
          <option value="Low">Low &lt;60%</option>
        </select>
      </div>
    </div>
  );
}
