import { Eye } from "lucide-react";

import type { Building } from "../types";
import StatusBadge from "./StatusBadge";

interface Props {
  buildings: Building[];
  onSelect: (building: Building) => void;
}

const columns = ["ID", "Street", "Type", "Floors", "OCR", "Match", "Confidence", "Status", ""];

export default function DiscrepancyTable({ buildings, onSelect }: Props) {
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
        <table className="w-full min-w-[850px] border-collapse">
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
            {buildings.map((building) => (
              <tr
                key={building.id}
                onClick={() => onSelect(building)}
                className="cursor-pointer border-b border-white/5 transition hover:bg-cyan-400/[0.04]"
              >
                <td className="px-5 py-4 text-sm font-bold text-white">{building.id}</td>
                <td className="px-5 py-4 text-sm text-slate-300">{building.street}</td>
                <td className="px-5 py-4 text-sm text-slate-300">{building.buildingType ?? building.type}</td>
                <td className="px-5 py-4 text-sm font-semibold text-slate-200">{building.floors}</td>
                <td className="max-w-[160px] truncate px-5 py-4 text-sm text-slate-400">{building.ocr}</td>
                <td className="px-5 py-4 text-sm font-semibold text-slate-200">{building.matchedProperty}</td>
                <td className="px-5 py-4 text-sm font-bold text-white">{building.confidence}%</td>
                <td className="px-5 py-4"><StatusBadge status={building.status} /></td>
                <td className="px-5 py-4">
                  <button
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
    </div>
  );
}
