import { Link } from "react-router-dom";
import { ArrowUpRight, Map as MapIcon, ShieldCheck, TrendingUp } from "lucide-react";

import KPICards from "../components/KPICards";
import ProcessingStatus from "../components/ProcessingStatus";
import StatusBadge from "../components/StatusBadge";
import { useDashboard } from "../context/DashboardContext";
import { reviewItems } from "../data/mockData";

export default function Overview() {
  const { discrepancies } = useDashboard();
  const topDiscrepancies = discrepancies.slice(0, 4);
  const topFindings = reviewItems.slice(0, 3);

  return (
    <div>
      {/* Hero */}
      <div className="relative mb-6 overflow-hidden rounded-3xl border border-white/8 bg-gradient-to-br from-[#101532] via-[#161a44] to-[#241457] p-7 sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -left-10 bottom-[-4rem] h-56 w-56 rounded-full bg-violet-500/10 blur-3xl" />

        <div className="relative flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <span className="text-[10px] font-bold tracking-widest text-cyan-400">URBANLENS AI</span>
            <h1 className="m-0 mb-1.5 mt-2 bg-gradient-to-r from-white to-slate-300 bg-clip-text text-3xl font-extrabold tracking-tight text-transparent sm:text-4xl">
              City Intelligence Dashboard
            </h1>
            <p className="m-0 max-w-2xl text-[13px] leading-relaxed text-slate-400">
              Monitor buildings, infrastructure assets, property matching and AI verification across the
              selected study area.
            </p>

            <div className="mt-5 flex flex-wrap gap-2.5">
              <Link
                to="/map"
                className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-indigo-900/30 transition hover:brightness-110"
              >
                <MapIcon size={14} /> Open Map Intelligence
              </Link>
              <Link
                to="/review"
                className="flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-bold text-slate-200 transition hover:bg-white/10"
              >
                <ShieldCheck size={14} /> Go to Review Queue
              </Link>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3 rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400" />
            <div>
              <strong className="block text-[13px] font-bold text-emerald-300">Analysis Active</strong>
              <span className="block text-[10px] text-emerald-400/70">Street View intelligence pipeline running</span>
            </div>
          </div>
        </div>
      </div>

      <KPICards />

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ProcessingStatus />

        {/* Top discrepancies preview */}
        <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-bold tracking-widest text-red-400">NEEDS ATTENTION</span>
              <h3 className="m-0 mt-1 text-sm font-bold text-white">Top Property Discrepancies</h3>
            </div>
            <Link to="/properties" className="flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300">
              View all <ArrowUpRight size={13} />
            </Link>
          </div>

          <div className="flex flex-col gap-2.5">
            {topDiscrepancies.map((b) => (
              <div
                key={b.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-white/6 bg-white/[0.02] px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <strong className="text-[13px] font-bold text-white">{b.id}</strong>
                    <span className="truncate text-xs text-slate-500">{b.street}</span>
                  </div>
                  <span className="text-[11px] text-slate-500">{b.buildingType ?? b.type} · {b.floors} floors</span>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs font-bold text-slate-300">{b.confidence}%</span>
                  <StatusBadge status={b.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold tracking-widest text-orange-400">HUMAN-IN-THE-LOOP</span>
            <h3 className="m-0 mt-1 text-sm font-bold text-white">Pending Review Highlights</h3>
          </div>
          <Link to="/review" className="flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300">
            Open queue <ArrowUpRight size={13} />
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {topFindings.map((item) => (
            <div key={item.id} className="rounded-xl border border-white/6 bg-white/[0.02] p-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-cyan-400">{item.id}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                    item.priority === "High" ? "bg-red-400/15 text-red-400" : "bg-orange-400/15 text-orange-400"
                  }`}
                >
                  {item.priority}
                </span>
              </div>
              <p className="m-0 mt-2 text-[13px] font-semibold leading-snug text-white">{item.title}</p>
              <div className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-500">
                <TrendingUp size={12} /> {item.confidence}% confidence
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
