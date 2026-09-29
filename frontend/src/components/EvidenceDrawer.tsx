import type { ReactNode } from "react";
import {
  Building2,
  CheckCircle2,
  MapPin,
  ScanText,
  Sparkles,
  X,
} from "lucide-react";

import { useDashboard } from "../context/DashboardContext";
import StatusBadge from "./StatusBadge";

function InfoCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white/[0.04] p-3.5">
      <div className="flex items-center gap-2 text-[10px] text-slate-500">
        {icon}
        {label}
      </div>
      <p className="m-0 mt-1.5 text-sm font-bold text-white">{value}</p>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h3 className="m-0 text-[10px] font-bold uppercase tracking-widest text-slate-500">{title}</h3>;
}

export default function EvidenceDrawer() {
  const { selectedBuilding: building, isDrawerOpen, closeDrawer } = useDashboard();

  return (
    <>
      <div
        onClick={closeDrawer}
        className={`fixed inset-0 z-[900] bg-black/50 backdrop-blur-[2px] transition-opacity duration-300 ${
          isDrawerOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        className={`fixed right-0 top-0 z-[901] h-screen w-full max-w-[420px] overflow-y-auto border-l border-white/10 bg-[#0d1128] p-6 shadow-[-20px_0_60px_rgba(0,0,0,0.5)] transition-transform duration-300 ease-out ${
          isDrawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {building && (
          <>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-cyan-400/10 px-2 py-0.5 text-[10px] font-bold text-cyan-400">BUILDING</span>
                  <span className="text-[10px] text-slate-500">Evidence Record</span>
                </div>
                <h2 className="m-0 mt-2.5 text-xl font-extrabold text-white">{building.id}</h2>
              </div>
              <button onClick={closeDrawer} className="rounded-lg p-1.5 text-slate-500 transition hover:bg-white/10 hover:text-white">
                <X size={18} />
              </button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2.5">
              <InfoCard icon={<Building2 size={14} />} label="Building Type" value={building.buildingType ?? building.type} />
              <InfoCard icon={<MapPin size={14} />} label="Street" value={building.street} />
              <InfoCard icon={<Building2 size={14} />} label="Visible Floors" value={`${building.floors}`} />
              <InfoCard icon={<Sparkles size={14} />} label="Confidence" value={`${building.confidence}%`} />
            </div>

            <div className="mt-2.5">
              <InfoCard
                icon={<MapPin size={14} />}
                label="Approximate Location"
                value={`${building.latitude.toFixed(4)}, ${building.longitude.toFixed(4)}`}
              />
            </div>

            <div className="mt-5">
              <SectionTitle title="OCR Evidence" />
              <div className="mt-2.5 rounded-xl bg-black/40 p-3.5">
                <div className="flex items-center gap-1.5 text-[11px] text-cyan-300">
                  <ScanText size={13} /> Detected Text
                </div>
                <p className="m-0 mt-2 text-base font-bold tracking-wide text-white">{building.ocr}</p>
              </div>
            </div>

            <div className="mt-5">
              <SectionTitle title="Property Matching" />
              <div className="mt-2.5 rounded-xl border border-white/8 p-3.5">
                <div className="flex justify-between">
                  <span className="text-xs text-slate-400">Matched Property</span>
                  <span className="text-sm font-bold text-white">{building.matchedProperty}</span>
                </div>
                <div className="mt-3">
                  <div className="mb-1.5 flex justify-between text-[10px]">
                    <span className="text-slate-500">Match Score</span>
                    <span className="font-bold text-cyan-400">{building.matchScore}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-indigo-400"
                      style={{ width: `${building.matchScore}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5">
              <SectionTitle title="AI Processing" />
              <div className="mt-2.5 flex items-center gap-2 rounded-xl bg-violet-400/10 p-3.5 text-sm font-semibold text-violet-300">
                <Sparkles size={15} />
                {building.processing}
              </div>
            </div>

            <div className="mt-5 flex items-center gap-2">
              <CheckCircle2 size={16} className="text-slate-500" />
              <StatusBadge status={building.status} />
            </div>
          </>
        )}
      </aside>
    </>
  );
}
