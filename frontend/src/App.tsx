import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { DashboardProvider } from "./context/DashboardContext";
import AppLayout from "./layouts/AppLayout";
import { AuthProvider } from "./auth/AuthProvider";
import { LoginOnly, RequireAuth, RequirePermission } from "./auth/RouteGuards";
import LoginPage from "./pages/LoginPage";
import AccessDeniedPage from "./pages/AccessDeniedPage";

const Overview = lazy(() => import("./pages/Overview"));
const MapIntelligence = lazy(() => import("./pages/MapIntelligence"));
const Properties = lazy(() => import("./pages/Properties"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const AnalysisHistoryPage = lazy(() => import("./pages/AnalysisHistoryPage"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ChallengeQueriesPage = lazy(() => import("./pages/ChallengeQueriesPage"));
const UserManagementPage = lazy(() => import("./pages/UserManagementPage"));

function LazyPageOutlet() {
  return <Suspense fallback={<p role="status" className="p-6 text-sm text-slate-300">Loading page…</p>}><Outlet /></Suspense>;
}

function AuthenticatedLayout() {
  return <DashboardProvider><AppLayout /></DashboardProvider>;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<LoginOnly />}><Route path="/login" element={<LoginPage />} /></Route>
          <Route element={<RequireAuth />}>
            <Route path="/403" element={<AccessDeniedPage />} />
            <Route element={<AuthenticatedLayout />}>
              <Route element={<RequirePermission />}>
                <Route element={<LazyPageOutlet />}>
            <Route path="/" element={<Overview />} />
            <Route path="/map" element={<MapIntelligence />} />
            <Route path="/properties" element={<Properties />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/history" element={<AnalysisHistoryPage />} />
            <Route path="/challenge-queries" element={<ChallengeQueriesPage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin/users" element={<UserManagementPage />} />
                </Route>
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
