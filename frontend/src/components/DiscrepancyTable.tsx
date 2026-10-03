import { useState } from "react";
import { Eye } from "lucide-react";

import type { Building } from "../types";
import StatusBadge from "./StatusBadge";
import PaginationControls from "./PaginationControls";
import { paginate } from "../utils/pagination";

interface Props {
  buildings: Building[];
  onSelect: (building: Building) => void;
}

const columns = ["ID", "Street", "Location", "Entity", "Floors / use", "OCR", "Match", "Position", "Confidence", "Discrepancy / review", "Route / source", ""];

export default function DiscrepancyTable({ buildings, onSelect }: Props) {
  const pageSize = 25;
  const [page, setPage] = useState(1);
  const current = paginate(buildings, page, pageSize);
  return (
    <div className="overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03]">
      <div className="flex flex-col justify-between gap-3 border-b border-white/8 p-5 sm:flex-row sm:items-center">
        <div>
          <h2 className="m-0 text-base font-bold text-white">Discrepancy &amp; Matching Review</h2>
          <p className="m-0 mt-1 text-xs text-slate-500">
            {buildings.length} buildings requiring verification or review
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[1450px] border-collapse">
          <thead>
            <tr className="border-b border-white/8 bg-white/[0.02] text-left">
              {columns.map((col) => (
                <th key={col} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {buildings.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-5 py-10 text-center text-sm text-slate-500">
                  No records match the current filters.
                </td>
              </tr>
            )}
            {current.items.map((building) => (
              <tr
                key={building.id}
                onClick={() => onSelect(building)}
                className="cursor-pointer border-b border-white/5 transition hover:bg-cyan-400/[0.04]"
              >
                <td className="px-5 py-4 text-sm font-bold text-white">{building.id}</td>
                <td className="px-5 py-4 text-sm text-slate-300">{building.street}</td>
                <td className="px-5 py-4 text-xs text-slate-400">{building.latitude == null || building.longitude == null
                  ? "Location unavailable" : `${building.latitude.toFixed(5)}, ${building.longitude.toFixed(5)}`}</td>
                <td className="px-5 py-4 text-sm text-slate-300">{building.assetType}</td>
                <td className="px-5 py-4 text-xs text-slate-300">{building.floors == null ? (building.floorStatus === "unknown" ? "Unknown" : "Not detected") : building.floors} · {String(building.attributes?.building_use ?? "unknown")}</td>
                <td className="max-w-[160px] truncate px-5 py-4 text-sm text-slate-400">{building.ocr}</td>
                <td className="px-5 py-4 text-sm font-semibold text-slate-200">{building.matchedProperty}</td>
                <td className="px-5 py-4 text-xs text-slate-400">{building.positionConfidence == null ? "Unvalidated" : `${Math.round(building.positionConfidence * 100)}%`}</td>
                <td className="px-5 py-4 text-sm font-bold text-white">{building.confidence == null ? "Unavailable" : `${building.confidence}%`}</td>
                <td className="max-w-[220px] px-5 py-4 text-xs text-slate-400">{building.discrepancy || building.reviewStatus}</td>
                <td className="px-5 py-4 text-xs text-slate-400">{building.modelRoute} · {building.provenance}</td>
                <td className="px-5 py-4">
                  <StatusBadge status={building.status} />
                  <button
                    aria-label={`View evidence for ${building.id}`}
                    onClick={(e) => { e.stopPropagation(); onSelect(building); }}
                    className="rounded-lg p-2 text-slate-500 transition hover:bg-white/10 hover:text-cyan-400"
                  >
                    <Eye size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationControls page={current.page} pageCount={current.pageCount} total={current.total} pageSize={pageSize} onPageChange={setPage} />
    </div>
  );
}
