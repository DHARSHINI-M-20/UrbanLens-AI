import { AlertTriangle, Check, Pencil, X } from "lucide-react";
import { useState } from "react";

import { useDashboard } from "../context/DashboardContext";
import type { ReviewAction, ReviewItem } from "../types";
import PaginationControls from "./PaginationControls";
import { paginate } from "../utils/pagination";

const actionLabels: Record<ReviewAction, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  rejected: "Rejected",
  corrected: "Corrected",
};

const actionStyles: Record<ReviewAction, string> = {
  pending: "bg-white/8 text-slate-300",
  confirmed: "bg-emerald-400/15 text-emerald-400",
  rejected: "bg-red-400/15 text-red-400",
  corrected: "bg-cyan-400/15 text-cyan-400",
};

export default function ReviewQueue({ items, readOnly = false }: { items: ReviewItem[]; readOnly?: boolean }) {
  const { decideReview, busy } = useDashboard();
  const [corrections, setCorrections] = useState<Record<string, Record<string, string>>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const pageSize = 10;
  const [page, setPage] = useState(1);
  const current = paginate(items, page, pageSize);
  const pendingCount = items.filter((item) => !["approved", "rejected", "corrected"].includes(item.status ?? "pending")).length;

  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="m-0 text-[10px] font-bold uppercase tracking-widest text-orange-400">AUTOMATED FINDINGS</p>
          <h2 className="m-0 mt-1 text-lg font-bold text-white">Review Queue</h2>
          <p className="m-0 mt-1 text-xs text-slate-500">{pendingCount} of {items.length} awaiting a decision</p>
        </div>
        <div className="rounded-xl bg-orange-400/10 p-2.5 text-orange-400">
          <AlertTriangle size={19} />
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {items.length === 0 && <p className="m-0 py-8 text-center text-sm text-slate-500">No observations currently require review.</p>}
        {current.items.map((item) => {
          const action = item.status === "corrected" ? "corrected" : item.status === "approved" ? "confirmed" : item.status === "rejected" ? "rejected" : "pending";
          const evidence = item.rawRecord ?? {};
          const observation = (evidence.observation ?? {}) as Record<string, unknown>;
          const discrepancy = (evidence.discrepancy ?? {}) as Record<string, unknown>;
          const reference = (evidence.reference ?? {}) as Record<string, unknown>;
          return (
            <div
              key={item.id}
              className="rounded-xl border border-white/8 bg-white/[0.02] p-4 transition hover:border-orange-400/25"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="m-0 text-[11px] font-bold text-cyan-400">{item.id}{item.buildingId ? ` · ${item.buildingId}` : ""}</p>
                  <h3 className="m-0 mt-1 text-sm font-bold text-white">{item.title}</h3>
                  {item.detail && <p className="m-0 mt-1 text-xs font-semibold text-slate-400">{item.detail}</p>}
                  <p className="m-0 mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
                  <p className="m-0 mt-2 text-[11px] text-slate-400">
                    {String(observation.asset_type ?? "Observation")} · {String(observation.observation_id ?? item.observationId)} · OCR: {String(observation.ocr_text ?? "none")}
                  </p>
                  <p className="m-0 mt-1 text-[11px] text-slate-500">
                    Match: {String(observation.match_status ?? "unmatched")} · reference: {String(reference.reference_id ?? "none")}
                  </p>
                  {Boolean(discrepancy.description) && <p className="m-0 mt-1 text-[11px] text-amber-200/80">{String(discrepancy.description)}</p>}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <span
                    className={`rounded-full px-2 py-1 text-[10px] font-bold ${
                      item.priority === "High" ? "bg-red-400/15 text-red-400" : "bg-orange-400/15 text-orange-400"
                    }`}
                  >
                    {item.priority}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${actionStyles[action]}`}>
                    {actionLabels[action]}
                  </span>
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <span className="text-[11px] text-slate-500">Confidence</span>
                <span className="text-xs font-bold text-slate-200">{item.confidence == null ? "Not available" : `${item.confidence}%`}</span>
              </div>
              <div className="mt-1.5 h-1.5 rounded-full bg-white/8">
                {item.confidence != null && <div className="h-full rounded-full bg-orange-400" style={{ width: `${item.confidence}%` }} />}
              </div>

              {!readOnly && <details className="mt-3 rounded-lg border border-white/10 p-3">
                <summary className="cursor-pointer text-xs font-semibold text-slate-300">Optional correction and reviewer note</summary>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {[["visible_floor_count", "Corrected floor count"], ["building_use", "Corrected building use"], ["asset_type", "Corrected asset type"], ["ocr_text", "Corrected OCR text"]].map(([key, label]) => <label key={key} className="text-[10px] text-slate-500">{label}<input value={corrections[item.id]?.[key] ?? ""} onChange={(event) => setCorrections((current) => ({ ...current, [item.id]: { ...current[item.id], [key]: event.target.value } }))} className="mt-1 w-full rounded border border-white/10 bg-black/20 px-2 py-1.5 text-xs text-white" /></label>)}
                  <label className="text-[10px] text-slate-500 sm:col-span-2">Reviewer note<textarea value={notes[item.id] ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))} maxLength={2000} className="mt-1 w-full rounded border border-white/10 bg-black/20 px-2 py-1.5 text-xs text-white" /></label>
                </div>
              </details>}
              {!readOnly ? <div className="mt-3.5 grid grid-cols-3 gap-2">
                <button
                  disabled={busy || action === "confirmed"}
                  onClick={() => void decideReview(item, "approved", "confirmed", {}, notes[item.id]?.trim())}
                  className={`flex items-center justify-center gap-1.5 rounded-lg py-2 text-[11px] font-bold transition ${
                    action === "confirmed" ? "bg-emerald-500 text-white" : "bg-white/6 text-slate-300 hover:bg-emerald-500/20 hover:text-emerald-300"
                  }`}
                >
                  <Check size={13} /> Confirm
                </button>
                <button
                  disabled={busy || action === "rejected"}
                  onClick={() => void decideReview(item, "rejected", "rejected", {}, notes[item.id]?.trim())}
                  className={`flex items-center justify-center gap-1.5 rounded-lg py-2 text-[11px] font-bold transition ${
                    action === "rejected" ? "bg-red-500 text-white" : "bg-white/6 text-slate-300 hover:bg-red-500/20 hover:text-red-300"
                  }`}
                >
                  <X size={13} /> Reject
                </button>
                <button
                  disabled={busy || action === "confirmed"}
                  onClick={() => {
                    const fields = corrections[item.id] ?? {};
                    const payload: Record<string, unknown> = {};
                    for (const key of ["building_use", "asset_type", "ocr_text"] as const) if (fields[key]?.trim()) payload[key] = fields[key].trim();
                    if (fields.visible_floor_count?.trim() && Number.isInteger(Number(fields.visible_floor_count)) && Number(fields.visible_floor_count) >= 0) payload.visible_floor_count = Number(fields.visible_floor_count);
                    void decideReview(item, "approved", "corrected", payload, notes[item.id]?.trim());
                  }}
                  className={`flex items-center justify-center gap-1.5 rounded-lg py-2 text-[11px] font-bold transition ${
                    action === "corrected" ? "bg-cyan-500 text-white" : "bg-white/6 text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300"
                  }`}
                >
                  <Pencil size={13} /> Correct
                </button>
              </div> : <p className="m-0 mt-3.5 text-[11px] text-slate-500">AWS cloud review records are read-only in this dashboard.</p>}
            </div>
          );
        })}
      </div>
      <PaginationControls page={current.page} pageCount={current.pageCount} total={current.total} pageSize={pageSize} onPageChange={setPage} />
    </div>
  );
}
