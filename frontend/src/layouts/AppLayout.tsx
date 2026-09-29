import { Outlet, useLocation } from "react-router-dom";

import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import EvidenceDrawer from "../components/EvidenceDrawer";
import DemoModeBanner from "../components/DemoModeBanner";

export default function AppLayout() {
  const location = useLocation();

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-[#0b1020]">
      {/* Decorative ambient glows */}
      <div className="pointer-events-none fixed left-[18%] top-[-10%] z-0 h-[420px] w-[420px] rounded-full bg-indigo-600/20 blur-[120px]" />
      <div className="pointer-events-none fixed right-[5%] top-[20%] z-0 h-[380px] w-[380px] rounded-full bg-cyan-500/10 blur-[130px]" />
      <div className="pointer-events-none fixed bottom-[-10%] left-[40%] z-0 h-[420px] w-[420px] rounded-full bg-violet-600/10 blur-[140px]" />

      <div className="relative z-10 flex w-full">
        <Sidebar />

        <main className="min-w-0 flex-1">
          <Header />
          <DemoModeBanner />

          <div key={location.pathname} className="mx-auto max-w-[1700px] animate-page-in px-6 py-6 sm:px-8">
            <Outlet />
          </div>
        </main>
      </div>

      <EvidenceDrawer />
    </div>
  );
}
