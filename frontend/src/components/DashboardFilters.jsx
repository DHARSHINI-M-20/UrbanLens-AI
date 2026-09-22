import React from "react";

function DashboardFilters({
  location,
  setLocation,
  assetType,
  setAssetType,
  status,
  setStatus
}) {
  const resetFilters = () => {
    setLocation("All Locations");
    setAssetType("All Assets");
    setStatus("All Status");
  };

  return (
    <div className="dashboard-filters">

      <div className="filter-group">
        <label>Location</label>

        <select
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        >
          <option>All Locations</option>
          <option>Anna Nagar</option>
          <option>KK Nagar</option>
          <option>Tallakulam</option>
          <option>Mattuthavani</option>
        </select>
      </div>

      <div className="filter-group">
        <label>Asset Type</label>

        <select
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
        >
          <option>All Assets</option>
          <option>Building</option>
          <option>Road</option>
          <option>Property</option>
          <option>Infrastructure</option>
        </select>
      </div>

      <div className="filter-group">
        <label>Verification Status</label>

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option>All Status</option>
          <option>Verified</option>
          <option>Review</option>
          <option>Failed</option>
          <option>Processing</option>
        </select>
      </div>

      <button
        className="reset-filter"
        onClick={resetFilters}
      >
        Reset Filters
      </button>

    </div>
  );
}

export default DashboardFilters;