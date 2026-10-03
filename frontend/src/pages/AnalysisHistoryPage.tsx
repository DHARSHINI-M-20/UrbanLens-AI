import { CalendarClock } from "lucide-react";
import { useDashboard } from "../context/DashboardContext";
import { nullableNumber } from "../utils/recordValues";

export default function AnalysisHistoryPage() {
  const { runs, loading, error, seeded } = useDashboard();
  const simulatedCount = runs.filter((run) => Boolean(run.simulation)).length;
  const processedViewCounts = runs.map((run) => nullableNumber(run.processed_views));
  const processedViews = processedViewCounts.length === 0 ? 0 :
    processedViewCounts.some((value) => value == null) ? "Unavailable" :
      processedViewCounts.reduce<number>((sum, value) => sum + (value ?? 0), 0);
  return <div>
    <div className="mb-5"><span className="text-[10px] font-bold tracking-widest text-cyan-400">PERSISTED RUNS</span><h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Analysis History</h1><p className="m-0 mt-1 text-[13px] text-slate-500">Stored processing runs; simulated executions are labeled as such.</p></div>
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Stat title="Persisted runs" value={runs.length} />
      <Stat title="Simulated runs" value={simulatedCount} />
      <Stat title="Processed views" value={processedViews} />
    </div>
    {error && <p role="alert" className="rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-200">Run history unavailable: {error}</p>}
    {!loading && !error && !runs.length && <p className="rounded-xl border border-white/10 p-6 text-center text-sm text-slate-400">{seeded ? "No persisted processing runs are available." : "Seed the simulated demo dataset to create a run-history record."}</p>}
    {loading && <p role="status" className="text-sm text-slate-400">Loading persisted runs…</p>}
    {runs.length > 0 && <div className="overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.03]"><table className="w-full min-w-[650px] border-collapse text-left"><thead><tr className="border-b border-white/8 text-[10px] uppercase text-slate-500">{["Run", "Started", "Views", "Observations", "Status", "Source"].map((name) => <th key={name} className="px-4 py-3">{name}</th>)}</tr></thead><tbody>{runs.map((run, index) => <tr key={String(run.run_id ?? index)} className="border-b border-white/5 text-xs text-slate-300"><td className="px-4 py-3 font-semibold">{String(run.run_id ?? "Run ID unavailable")}</td><td className="px-4 py-3">{String(run.started_at ?? "Timestamp unavailable")}</td><td className="px-4 py-3">{String(run.processed_views ?? "Unavailable")}</td><td className="px-4 py-3">{String(run.observations ?? "Unavailable")}</td><td className="px-4 py-3">{run.simulation ? "SIMULATED" : String(run.status ?? "NOT_AVAILABLE")}</td><td className="px-4 py-3">{String(run.provenance ?? (run.simulation ? "Simulated demonstration data" : "Unavailable"))}</td></tr>)}</tbody></table></div>}
    <p className="mt-3 text-[11px] text-slate-500"><CalendarClock className="mr-1 inline" size={13} />Confidence is not shown as a run result because the persisted run record does not contain a validated aggregate confidence value.</p>
  </div>;
}

function Stat({ title, value }: { title: string; value: number | string }) {
  return <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{title}</div><p className="m-0 mt-2 text-2xl font-extrabold text-white">{value}</p></div>;
}
