import { NavLink } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { NAV_MAIN, NAV_MANAGEMENT, type NavItem } from "../data/navigation";

export default function Sidebar() {
  const renderItem = (item: NavItem) => {
    const Icon = item.icon;

    return (
      <NavLink
        key={item.id}
        to={item.path}
        end={item.path === "/"}
        className={({ isActive }) =>
          `group relative flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-[13px] font-medium transition-all duration-200 ${
            isActive
              ? "bg-gradient-to-r from-indigo-500/50 via-violet-500/20 to-transparent text-white"
              : "text-indigo-200/65 hover:translate-x-0.5 hover:bg-white/5 hover:text-white"
          }`
        }
      >
        {({ isActive }) => (
          <>
            {isActive && (
              <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-gradient-to-b from-cyan-300 to-violet-400 shadow-[0_0_10px_2px_rgba(129,140,248,0.6)]" />
            )}
            <Icon
              size={18}
              className={`shrink-0 transition-colors ${isActive ? "text-cyan-300" : "text-indigo-300/70 group-hover:text-cyan-200"}`}
            />
            <span>{item.label}</span>
          </>
        )}
      </NavLink>
    );
  };

  return (
    <aside className="sticky top-0 flex h-screen w-[252px] shrink-0 flex-col gap-6 overflow-y-auto border-r border-white/5 bg-gradient-to-b from-[#10132f] via-[#161a44] to-[#221254] px-4 py-6 text-white">
      <div className="flex items-center gap-3 border-b border-white/10 px-1.5 pb-5">
        <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400 via-indigo-500 to-violet-500 shadow-lg shadow-indigo-900/50">
          <Sparkles size={21} />
          <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-[#10132f] bg-emerald-400" />
        </div>
        <div>
          <h1 className="m-0 text-lg font-extrabold tracking-tight">UrbanLens</h1>
          <span className="text-[10px] tracking-wide text-indigo-300">AI INTELLIGENCE</span>
        </div>
      </div>

      <nav className="flex flex-col gap-1.5">
        <p className="px-3.5 pb-1 text-[10px] font-bold tracking-widest text-indigo-300/70">MAIN MENU</p>
        {NAV_MAIN.map(renderItem)}
      </nav>

      <nav className="flex flex-col gap-1.5">
        <p className="px-3.5 pb-1 text-[10px] font-bold tracking-widest text-indigo-300/70">MANAGEMENT</p>
        {NAV_MANAGEMENT.map(renderItem)}
      </nav>

      <div className="mt-auto flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/5 p-3">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,0.2)]" />
        <div className="min-w-0">
          <strong className="block truncate text-[11px] font-bold">AI Engine Online</strong>
          <span className="block truncate text-[10px] text-indigo-300">All systems operational</span>
        </div>
      </div>
    </aside>
  );
}
