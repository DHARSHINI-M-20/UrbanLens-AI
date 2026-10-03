import { lazy, Suspense } from "react";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import { DashboardProvider } from "./context/DashboardContext";
import AppLayout from "./layouts/AppLayout";

const Overview = lazy(() => import("./pages/Overview"));
const MapIntelligence = lazy(() => import("./pages/MapIntelligence"));
const Properties = lazy(() => import("./pages/Properties"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const AnalysisHistoryPage = lazy(() => import("./pages/AnalysisHistoryPage"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ChallengeQueriesPage = lazy(() => import("./pages/ChallengeQueriesPage"));

function LazyPageOutlet() {
  return <Suspense fallback={<p role="status" className="p-6 text-sm text-slate-300">Loading page…</p>}><Outlet /></Suspense>;
}

function App() {
  return (
    <DashboardProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route element={<LazyPageOutlet />}>
            <Route path="/" element={<Overview />} />
            <Route path="/map" element={<MapIntelligence />} />
            <Route path="/properties" element={<Properties />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/history" element={<AnalysisHistoryPage />} />
            <Route path="/challenge-queries" element={<ChallengeQueriesPage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </DashboardProvider>
  );
}

export default App;
