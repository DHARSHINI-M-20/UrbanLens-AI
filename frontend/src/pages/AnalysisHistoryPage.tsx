import { CalendarClock } from "lucide-react";

import StatusBadge from "../components/StatusBadge";
import { useDashboard } from "../context/DashboardContext";

export default function AnalysisHistoryPage() {
  const { metrics, views, observations } = useDashboard();
  const analysisHistory = metrics.map((metric) => {
    const viewId = String(metric.view_id ?? "view");
    const view = views.find((item) => item.view_id === viewId);
    const viewObservations = observations.filter((item) => item.source_view_id === viewId);
    const confidence = viewObservations.length
      ? Math.round(viewObservations.reduce((sum, item) => sum + Number(item.confidence ?? 0), 0) / viewObservations.length * 100)
      : 0;
    return {
      id: viewId,
      location: String(view?.street_id ?? "Simulated study area"),
      date: String(metric.timestamp ?? ""),
      buildings: Number(metric.buildings_detected ?? 0),
      assets: Number(metric.streetlights_detected ?? 0) + Number(metric.electric_poles_detected ?? 0),
      status: "Completed" as const,
      confidence,
    };
  });
  const averageConfidence = analysisHistory.length
    ? Math.round(analysisHistory.reduce((sum, run) => sum + run.confidence, 0) / analysisHistory.length)
    : 0;
  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">RUN LOG</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Analysis History</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">
          Previous street-corridor analysis runs and their outcomes.
        </p>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
            <CalendarClock size={13} /> Total Runs
          </div>
          <p className="m-0 mt-2 text-2xl font-extrabold text-white">{analysisHistory.length}</p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Avg. Confidence</div>
          <p className="m-0 mt-2 text-2xl font-extrabold text-white">
            {averageConfidence}%
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Buildings Analysed</div>
          <p className="m-0 mt-2 text-2xl font-extrabold text-white">
            {analysisHistory.reduce((sum, r) => sum + r.buildings, 0)}
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03]">
        <table className="w-full min-w-[700px] border-collapse">
          <thead>
            <tr className="border-b border-white/8 bg-white/[0.02] text-left">
              {["Run", "Location", "Date", "Buildings", "Assets", "Confidence", "Status"].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {analysisHistory.map((run) => (
              <tr key={run.id} className="border-b border-white/5 transition hover:bg-white/[0.03]">
                <td className="px-5 py-4 text-sm font-bold text-white">{run.id}</td>
                <td className="px-5 py-4 text-sm text-slate-300">{run.location}</td>
                <td className="px-5 py-4 text-sm text-slate-400">{run.date}</td>
                <td className="px-5 py-4 text-sm font-semibold text-slate-200">{run.buildings}</td>
                <td className="px-5 py-4 text-sm font-semibold text-slate-200">{run.assets}</td>
                <td className="px-5 py-4 text-sm font-bold text-white">{run.confidence}%</td>
                <td className="px-5 py-4"><StatusBadge status={run.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
