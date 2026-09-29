import { CheckCircle2, Cpu, Database, ScanLine } from "lucide-react";

const steps = [
  { icon: ScanLine, title: "Street View", subtitle: "Imagery collected", state: "done" as const },
  { icon: Cpu, title: "YOLO Detection", subtitle: "Objects detected", state: "done" as const },
  { icon: Database, title: "Property Matching", subtitle: "Analyzing records", state: "active" as const },
];

export default function ProcessingStatus() {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[10px] font-bold tracking-widest text-cyan-400">AI PIPELINE</span>
          <h3 className="m-0 mt-1 text-sm font-bold text-white">Processing Status</h3>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2.5 py-1 text-[10px] font-extrabold text-emerald-400">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          LIVE
        </div>
      </div>

      <div className="mt-5 flex flex-col">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isLast = index === steps.length - 1;
          return (
            <div key={step.title}>
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
                    step.state === "done"
                      ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-400"
                      : "border-cyan-400/30 bg-cyan-400/10 text-cyan-400"
                  }`}
                >
                  <Icon size={16} />
                </div>
                <div className="min-w-0 flex-1">
                  <strong className="block truncate text-[13px] font-bold text-white">{step.title}</strong>
                  <span className="block truncate text-[11px] text-slate-500">{step.subtitle}</span>
                </div>
                {step.state === "done" ? (
                  <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
                ) : (
                  <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
                )}
              </div>
              {!isLast && <div className="ml-[17px] h-4 w-px bg-white/10" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
