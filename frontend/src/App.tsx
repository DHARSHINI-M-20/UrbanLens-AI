import { BrowserRouter, Route, Routes } from "react-router-dom";

import { DashboardProvider } from "./context/DashboardContext";
import AppLayout from "./layouts/AppLayout";

import Overview from "./pages/Overview";
import MapIntelligence from "./pages/MapIntelligence";
import Properties from "./pages/Properties";
import AnalyticsPage from "./pages/AnalyticsPage";
import AnalysisHistoryPage from "./pages/AnalysisHistoryPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  return (
    <DashboardProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Overview />} />
            <Route path="/map" element={<MapIntelligence />} />
            <Route path="/properties" element={<Properties />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/history" element={<AnalysisHistoryPage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DashboardProvider>
  );
}

export default App;
