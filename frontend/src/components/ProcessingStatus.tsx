import { useDashboard } from "../context/DashboardContext";
import { nullableNumber } from "../utils/recordValues";

export default function ProcessingStatus() {
  const { summary, seeded, loading, busy, error } = useDashboard();
  const metrics = (summary?.processing_metrics ?? {}) as Record<string, unknown>;
  const processed = nullableNumber(metrics.total_views);
  const status = error ? "FAILED" : loading || busy ? "PROCESSING" : !seeded ? "IDLE" : processed != null && processed > 0 ? "SIMULATED" : "NOT_AVAILABLE";
  const statusColor = status === "FAILED" ? "text-red-300" : status === "SIMULATED" ? "text-amber-200" : "text-slate-300";
  return <section className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
    <div className="flex items-center justify-between gap-3">
      <div><span className="text-[10px] font-bold tracking-widest text-cyan-400">PIPELINE RECORDS</span><h3 className="m-0 mt-1 text-sm font-bold text-white">Processing Status</h3></div>
      <strong className={`rounded-full bg-white/5 px-2.5 py-1 text-[10px] ${statusColor}`}>{status}</strong>
    </div>
    <p className="mt-4 text-xs leading-5 text-slate-400">{status === "SIMULATED" ? "These persisted results came from deterministic simulated providers; this is not real Street View processing." : status === "IDLE" ? "No demo dataset is seeded." : status === "FAILED" ? "The API did not return current processing status." : status === "NOT_AVAILABLE" ? "No persisted processing metrics are available." : "Loading persisted processing metrics."}</p>
    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-white/8 pt-4 text-[11px]">
      <dt className="text-slate-500">Views in metrics</dt><dd className="m-0 text-right text-slate-200">{processed == null ? "Unavailable" : String(processed)}</dd>
      <dt className="text-slate-500">Average latency</dt><dd className="m-0 text-right text-slate-200">{metrics.average_latency_ms == null ? "Unavailable" : `${String(metrics.average_latency_ms)} ms`}</dd>
      <dt className="text-slate-500">Detector / OCR latency</dt><dd className="m-0 text-right text-slate-200">{metrics.detector_latency_ms == null || metrics.ocr_latency_ms == null ? "Unavailable" : `${String(metrics.detector_latency_ms)} / ${String(metrics.ocr_latency_ms)} ms`}</dd>
      <dt className="text-slate-500">Actual provider invocations</dt><dd className="m-0 text-right text-slate-200">{String(metrics.actual_invocation_count ?? "Unavailable")}</dd>
      <dt className="text-slate-500">Simulated fixture calls</dt><dd className="m-0 text-right text-amber-200">{String(metrics.simulated_fixture_invocation_count ?? "Unavailable")}</dd>
      <dt className="col-span-2 text-slate-500">{summary?.processing_cost_message ? String(summary.processing_cost_message) : "Cost unavailable unless verified provider pricing is configured."}</dt>
    </dl>
  </section>;
}
