import { RefreshCw, RotateCcw, Database, Play } from "lucide-react";

import { DEMO_BANNER, DEMO_DATASET_ID, useDashboard } from "../context/DashboardContext";

export default function DemoModeBanner() {
  const { apiMode, awsStatus, seeded, loading, busy, error, statusMessage, refresh, seedDemo, processDemo, resetDemo } = useDashboard();
  const awsBedrock = awsStatus?.bedrock as Record<string, unknown> | undefined;
  const confirmReset = () => {
    if (window.confirm("Delete only the simulated demo dataset from the local database?")) void resetDemo();
  };
  const confirmReseed = () => {
    if (window.confirm("Replace the existing simulated demo records with a fresh seeded run?")) void seedDemo();
  };

  return (
    <section className="mx-6 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300/30 bg-amber-200/[0.08] px-4 py-3 sm:mx-8">
      <div className="min-w-0">
        <strong className="block text-[11px] font-extrabold text-amber-200">
          OFFICIAL STUDY AREA · SYNTHETIC DEMONSTRATION DATA · NOT REAL STREET VIEW
        </strong>
        <span className="block whitespace-pre-line text-[11px] text-amber-100/75">{DEMO_BANNER}</span>
        <span className="mt-1 block text-[10px] text-amber-100/65">Dataset: {DEMO_DATASET_ID} · source mode: {apiMode === "aws" ? "AWS read API (live status not verified)" : "local API"}</span>
        {apiMode === "aws" && (
          <span className="mt-1 block text-[10px] text-emerald-200/80">
            AWS resource flags are configuration/status responses, not proof of current reachability. Bedrock execution: NOT VERIFIED{awsBedrock?.lambda_enabled ? " (enabled flag set)" : ""}.
          </span>
        )}
        {loading && <span role="status" className="mt-1 block text-[11px] text-slate-300">Loading dataset status…</span>}
        {error && <span role="alert" className="mt-1 block text-[11px] text-red-300">{apiMode === "aws" ? "Cloud API unavailable" : "Local API unavailable"}: {error} <button onClick={() => void refresh()} className="ml-1 underline" aria-label="Retry API request">Retry</button></span>}
        {!loading && !error && !seeded && <span className="mt-1 block text-[11px] text-slate-300">No dataset is seeded. Seed the local simulated demo to populate the dashboard.</span>}
        {statusMessage && <span className="mt-1 block text-[11px] text-emerald-300">{statusMessage}</span>}
      </div>
      {apiMode === "local" && <div className="flex shrink-0 gap-2">
        {!seeded ? (
          <button disabled={busy || loading} onClick={() => void seedDemo()}
            className="flex items-center gap-1.5 rounded-lg bg-amber-300 px-3 py-2 text-[11px] font-bold text-slate-950 disabled:opacity-50">
            <Database size={14} /> Seed demo
          </button>
        ) : (
          <>
            <button title="Process the existing simulated views" disabled={busy} onClick={() => void processDemo()}
              className="flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-2 text-[11px] font-bold text-white disabled:opacity-50">
              <Play size={13} /> Process
            </button>
            <button title="Reset and reseed only this fixed demo dataset" disabled={busy} onClick={confirmReseed}
              className="flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-2 text-[11px] font-bold text-white disabled:opacity-50">
              <RefreshCw size={13} /> Reseed
            </button>
            <button title="Remove only the simulated demo dataset" aria-label="Reset simulated demo dataset" disabled={busy} onClick={confirmReset}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/15 text-slate-300 disabled:opacity-50">
              <RotateCcw size={14} />
            </button>
          </>
        )}
      </div>}
    </section>
  );
}
