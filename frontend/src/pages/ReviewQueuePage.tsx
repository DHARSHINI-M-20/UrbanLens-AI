import ReviewQueue from "../components/ReviewQueue";
import { useDashboard } from "../context/DashboardContext";

export default function ReviewQueuePage() {
  const { reviews, apiMode } = useDashboard();
  return (
    <div>
      <div className="mb-5">
        <span className="text-[10px] font-bold tracking-widest text-cyan-400">HUMAN-IN-THE-LOOP</span>
        <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Review Queue</h1>
        <p className="m-0 mt-1 text-[13px] text-slate-500">
          {apiMode === "aws" ? "Cloud review records are read-only." : "Confirm, reject or correct low-confidence AI observations."}
        </p>
      </div>
      <ReviewQueue items={reviews} readOnly={apiMode === "aws"} />
    </div>
  );
}
