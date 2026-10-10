import { Link } from "react-router-dom";
import { Activity, ArrowUpRight, BarChart3, Building2, ClipboardCheck, FileSearch, Map, Settings, Users } from "lucide-react";

import KPICards from "../components/KPICards";
import ProcessingStatus from "../components/ProcessingStatus";
import { useDashboard } from "../context/DashboardContext";
import { useAuth } from "../auth/AuthProvider";
import { roleLabel } from "../auth/permissions";

const roleDashboard = {
  administrator: {
    title: "Platform Administration",
    description: "Monitor the UrbanLens workspace, manage accounts, and review platform activity.",
    actions: [
      { label: "Manage users and roles", detail: "Create accounts and assign access", to: "/admin/users", icon: Users },
      { label: "Platform settings", detail: "Configure authorized application settings", to: "/settings", icon: Settings },
      { label: "System analytics", detail: "Inspect coverage and processing reports", to: "/analytics", icon: BarChart3 },
      { label: "Review queue", detail: "See records awaiting verification", to: "/review", icon: ClipboardCheck },
    ],
  },
  analyst: {
    title: "Urban Analysis Workspace",
    description: "Explore buildings and street assets, inspect OCR and matching results, and compare analysis runs.",
    actions: [
      { label: "Map intelligence", detail: "Explore observed buildings and street assets", to: "/map", icon: Map },
      { label: "Properties and matching", detail: "Inspect OCR, confidence, and reference matches", to: "/properties", icon: Building2 },
      { label: "Analysis history", detail: "Review previous processing results", to: "/history", icon: Activity },
      { label: "Challenge queries", detail: "Search and filter the analysis dataset", to: "/challenge-queries", icon: FileSearch },
    ],
  },
  reviewer: {
    title: "Verification Desk",
    description: "Prioritize discrepancies and low-confidence observations for human review.",
    actions: [
      { label: "Open review queue", detail: "Verify discrepancies and add review decisions", to: "/review", icon: ClipboardCheck },
      { label: "Inspect properties", detail: "Open record evidence and matching details", to: "/properties", icon: Building2 },
      { label: "Map context", detail: "Check the location of an observation", to: "/map", icon: Map },
    ],
  },
  viewer: {
    title: "Urban Reports",
    description: "View authorized coverage, property summaries, maps, and read-only analytics.",
    actions: [
      { label: "View analytics", detail: "Read coverage and matching summaries", to: "/analytics", icon: BarChart3 },
      { label: "Explore map", detail: "Browse mapped observations", to: "/map", icon: Map },
      { label: "Browse properties", detail: "Read property and evidence details", to: "/properties", icon: Building2 },
    ],
  },
} as const;

export default function Overview() {
  const { user } = useAuth();
  const { discrepancies, reviews, seeded } = useDashboard();
  const role = user?.role ?? "viewer";
  const dashboard = roleDashboard[role];
  const openReviews = reviews.filter((review) => review.status === "pending").length;

  return (
    <div>
      <section className="relative mb-6 overflow-hidden rounded-3xl border border-white/8 bg-gradient-to-br from-[#101532] via-[#161a44] to-[#241457] p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <span className="text-[10px] font-bold tracking-widest text-cyan-400">{roleLabel(role).toUpperCase()} DASHBOARD</span>
            <h1 className="m-0 mb-1.5 mt-2 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">{dashboard.title}</h1>
            <p className="m-0 max-w-2xl text-[13px] leading-relaxed text-slate-400">{dashboard.description}</p>
          </div>
          <div className="shrink-0 rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3">
            <strong className="block text-[13px] font-bold text-emerald-300">{seeded ? "Demo pipeline ready" : "Demo dataset not seeded"}</strong>
            <span className="block text-[10px] text-emerald-400/70">Persisted records · simulation clearly labeled</span>
          </div>
        </div>
      </section>

      {role === "reviewer" && <section className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-orange-300/15 bg-orange-300/5 p-4"><span className="text-xs text-slate-400">Pending reviews</span><strong className="mt-1 block text-2xl text-white">{openReviews}</strong></div>
        <div className="rounded-2xl border border-red-300/15 bg-red-300/5 p-4"><span className="text-xs text-slate-400">Discrepancies</span><strong className="mt-1 block text-2xl text-white">{discrepancies.length}</strong></div>
        <div className="col-span-2 rounded-2xl border border-cyan-300/15 bg-cyan-300/5 p-4 sm:col-span-1"><span className="text-xs text-slate-400">Review access</span><strong className="mt-1 block text-sm text-cyan-200">Authorized records</strong></div>
      </section>}

      <section aria-label={`${roleLabel(role)} dashboard shortcuts`} className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {dashboard.actions.map(({ label, detail, to, icon: Icon }) => (
          <Link key={to} to={to} className="group rounded-2xl border border-white/8 bg-white/[0.03] p-4 transition hover:border-cyan-300/30 hover:bg-white/[0.06]">
            <div className="flex items-center justify-between"><Icon size={19} className="text-cyan-300" /><ArrowUpRight size={15} className="text-slate-500 group-hover:text-cyan-200" /></div>
            <strong className="mt-4 block text-sm text-white">{label}</strong>
            <span className="mt-1 block text-xs leading-5 text-slate-400">{detail}</span>
          </Link>
        ))}
      </section>

      <KPICards />
      {(role === "administrator" || role === "analyst") && <div className="mt-5"><ProcessingStatus /></div>}
      {role !== "viewer" && <section className="mt-5 rounded-2xl border border-white/8 bg-white/[0.03] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><span className="text-[10px] font-bold tracking-widest text-orange-300">RECORDS TO INSPECT</span><h2 className="m-0 mt-1 text-sm font-bold text-white">Discrepancies and verification</h2></div>
          <Link to={role === "reviewer" ? "/review" : "/properties"} className="flex items-center gap-1 text-xs font-bold text-cyan-300">Open records <ArrowUpRight size={13} /></Link>
        </div>
        <p className="mb-0 mt-3 text-xs leading-5 text-slate-400">{discrepancies.length} discrepancy records and {openReviews} pending review items are currently available in the loaded dataset.</p>
      </section>}
      {role === "viewer" && <p className="mt-5 rounded-xl border border-white/8 bg-white/[0.02] p-4 text-xs leading-5 text-slate-400">Viewer access is read-only. Reports and record details are available; review decisions and administrative changes are disabled.</p>}
    </div>
  );
}
