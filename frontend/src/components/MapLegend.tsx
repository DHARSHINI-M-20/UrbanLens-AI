const items: { label: string; color: string }[] = [
  { label: "Matched", color: "#22c55e" },
  { label: "Partial", color: "#f59e0b" },
  { label: "Unmatched", color: "#ef4444" },
  { label: "Low Confidence", color: "#f97316" },
  { label: "Not Verified", color: "#94a3b8" },
];

export default function MapLegend() {
  return (
    <div className="absolute left-4 top-4 z-[400] rounded-xl border border-white/10 bg-[#0f172a]/90 p-3.5 backdrop-blur-md">
      <div className="mb-2 text-[9px] font-extrabold tracking-widest text-slate-400">STATUS</div>
      <div className="flex flex-col gap-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-[11px] font-medium text-slate-200">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: item.color, boxShadow: `0 0 0 3px ${item.color}22` }}
            />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
