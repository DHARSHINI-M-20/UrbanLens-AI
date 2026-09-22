import { useState } from "react";

import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import KPICard from "../components/KPICard";
import MapView from "../components/MapView";
import UrbanTrendsChart from "../components/UrbanTrendsChart";
import PropertyInsights from "../components/PropertyInsights";
import AIVerification from "../components/AIVerification";
import RecentAnalysis from "../components/RecentAnalysis";
import DashboardFilters from "../components/DashboardFilters";

import { kpiData } from "../data/mockData";

export default function Dashboard() {

  const [location, setLocation] = useState("All Locations");
  const [assetType, setAssetType] = useState("All Assets");
  const [status, setStatus] = useState("All Status");

  return (
    <div className="app-layout">

      <Sidebar />

      <main className="main-content">

        <Header />

        <section className="dashboard-content">

          {/* Welcome Section */}
          <div className="welcome-section">

            <div>
              <h2>City Intelligence Overview</h2>

              <p>
                Monitor buildings, infrastructure assets, property matching,
                and AI verification results.
              </p>
            </div>

            <button className="analyse-btn">
              + Start Analysis
            </button>

          </div>

          {/* Dashboard Filters */}
          <DashboardFilters
            location={location}
            setLocation={setLocation}
            assetType={assetType}
            setAssetType={setAssetType}
            status={status}
            setStatus={setStatus}
          />

          {/* KPI Cards */}
          <div className="kpi-grid">

            {kpiData.map((item) => (
              <KPICard
                key={item.title}
                title={item.title}
                value={item.value}
                icon={item.icon}
                description={item.description}
              />
            ))}

          </div>

          {/* Map */}
          <MapView />

          {/* Urban Development Trends */}
          <UrbanTrendsChart />

          {/* Property & Infrastructure Insights */}
          <PropertyInsights />

          {/* AI Verification Summary */}
          <AIVerification />

          {/* Recent AI Analysis */}
          <RecentAnalysis
            location={location}
            assetType={assetType}
            status={status}
          />

        </section>

      </main>

    </div>
  );
}