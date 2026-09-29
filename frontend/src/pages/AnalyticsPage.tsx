import Analytics from "../components/Analytics";

export default function AnalyticsPage() {
  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">ANALYTICS</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Street-Level Intelligence</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">
          Analyse building use, floors, assets, matching confidence and AI routing.
        </p>
      </div>
      <Analytics />
    </div>
  );
}
