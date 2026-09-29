import type { Status } from "../types";

const styles: Record<string, string> = {
  MATCHED: "bg-emerald-400/10 text-emerald-400",
  Completed: "bg-emerald-400/10 text-emerald-400",
  PARTIAL: "bg-amber-400/10 text-amber-400",
  Review: "bg-amber-400/10 text-amber-400",
  UNMATCHED: "bg-red-400/10 text-red-400",
  "LOW CONFIDENCE": "bg-orange-400/10 text-orange-400",
  "NOT VERIFIED": "bg-slate-400/10 text-slate-300",
  Processing: "bg-cyan-400/10 text-cyan-400",
};

export default function StatusBadge({ status }: { status: Status | string }) {
  const style = styles[status] ?? "bg-slate-400/10 text-slate-300";
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[10px] font-bold ${style}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}
