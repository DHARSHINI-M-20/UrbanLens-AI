import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  description: string;
  accent: string;
}

export default function KPICard({ title, value, icon: Icon, description, accent }: KPICardProps) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-b from-white/[0.06] to-white/[0.02] p-5 transition hover:border-white/15 hover:-translate-y-0.5">
      <div
        className="pointer-events-none absolute -right-6 -top-10 h-28 w-28 rounded-full opacity-20 blur-2xl transition group-hover:opacity-30"
        style={{ background: accent }}
      />
      <div className="flex items-center justify-between">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-xl border"
          style={{ background: `${accent}1a`, borderColor: `${accent}33`, color: accent }}
        >
          <Icon size={18} />
        </div>
        <span className="rounded-md bg-emerald-400/10 px-1.5 py-0.5 text-[9px] font-extrabold tracking-wider text-emerald-400">
          LIVE
        </span>
      </div>

      <div className="mt-4 text-2xl font-extrabold tracking-tight text-white">{value}</div>
      <div className="mt-1 text-[13px] font-semibold text-slate-300">{title}</div>
      <div className="mt-1 text-[11px] text-slate-500">{description}</div>
    </div>
  );
}
