import { RefreshCw, RotateCcw, Database, Play } from "lucide-react";

import { DEMO_BANNER, useDashboard } from "../context/DashboardContext";

export default function DemoModeBanner() {
  const { seeded, loading, busy, error, statusMessage, seedDemo, processDemo, resetDemo } = useDashboard();

  return (
    <section className="mx-6 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300/30 bg-amber-200/[0.08] px-4 py-3 sm:mx-8">
      <div className="min-w-0">
        <strong className="block text-[11px] font-extrabold text-amber-200">SIMULATED DEMONSTRATION MODE</strong>
        <span className="block text-[11px] text-amber-100/75">{DEMO_BANNER}. Data is synthetic and is not Google Street View imagery.</span>
        {error && <span role="alert" className="mt-1 block text-[11px] text-red-300">API: {error}</span>}
        {statusMessage && <span className="mt-1 block text-[11px] text-emerald-300">{statusMessage}</span>}
      </div>
      <div className="flex shrink-0 gap-2">
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
            <button title="Reset and reseed only this fixed demo dataset" disabled={busy} onClick={() => void seedDemo()}
              className="flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-2 text-[11px] font-bold text-white disabled:opacity-50">
              <RefreshCw size={13} /> Reseed
            </button>
            <button title="Remove only the simulated demo dataset" disabled={busy} onClick={() => void resetDemo()}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/15 text-slate-300 disabled:opacity-50">
              <RotateCcw size={14} />
            </button>
          </>
        )}
      </div>
    </section>
  );
}
