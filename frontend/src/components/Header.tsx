import { useLocation } from "react-router-dom";
import { Bell, ChevronDown, Command, Search } from "lucide-react";

import { NAV_MAIN, NAV_MANAGEMENT } from "../data/navigation";
import { useDashboard } from "../context/DashboardContext";

const ALL_NAV = [...NAV_MAIN, ...NAV_MANAGEMENT];

export default function Header() {
  const { pathname } = useLocation();
  const { search, setSearch } = useDashboard();

  const current = ALL_NAV.find((n) => n.path === pathname);
  const activeLabel = current?.label ?? "Dashboard";

  return (
    <header className="sticky top-0 z-40 flex h-[76px] items-center justify-between gap-4 border-b border-white/5 bg-[#0b1020]/85 px-6 backdrop-blur-md sm:px-8">
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>UrbanLens AI</span>
        <span className="text-slate-600">/</span>
        <strong className="font-semibold text-white">{activeLabel}</strong>
      </div>

      <div className="flex flex-1 items-center justify-end gap-3">
        <div className="hidden max-w-sm flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2.5 transition focus-within:border-cyan-400/40 sm:flex">
          <Search size={16} className="text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            type="text"
            placeholder="Search buildings, streets, OCR..."
            className="w-full bg-transparent text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none"
          />
          <div className="flex items-center gap-0.5 rounded-md bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold text-slate-400">
            <Command size={10} />K
          </div>
        </div>

        <button className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10">
          <Bell size={18} />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-cyan-400" />
        </button>

        <button className="flex shrink-0 items-center gap-2.5 rounded-xl border border-white/10 bg-white/5 py-1.5 pl-1.5 pr-3 transition hover:bg-white/10">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-violet-500 text-xs font-extrabold text-white">
            TS
          </div>
          <div className="hidden text-left sm:block">
            <strong className="block text-xs font-bold leading-tight text-white">Urban Analyst</strong>
            <span className="block text-[10px] leading-tight text-slate-400">Administrator</span>
          </div>
          <ChevronDown size={14} className="hidden text-slate-500 sm:block" />
        </button>
      </div>
    </header>
  );
}
