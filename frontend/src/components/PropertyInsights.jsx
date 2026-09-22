import React from "react";

const propertyData = [
  {
    type: "Residential",
    total: 520,
    verified: 468,
    status: "Verified"
  },
  {
    type: "Commercial",
    total: 310,
    verified: 279,
    status: "Verified"
  },
  {
    type: "Industrial",
    total: 180,
    verified: 144,
    status: "Review"
  },
  {
    type: "Public Infrastructure",
    total: 240,
    verified: 216,
    status: "Verified"
  }
];

function PropertyInsights() {
  return (
    <div className="property-insights">

      <div className="section-header">
        <div>
          <h2>Property & Infrastructure Insights</h2>
          <p>
            Overview of detected properties and AI verification status.
          </p>
        </div>
      </div>

      <div className="property-table">

        <div className="table-header">
          <span>Property Type</span>
          <span>Total</span>
          <span>Verified</span>
          <span>Status</span>
        </div>

        {propertyData.map((item) => (
          <div className="table-row" key={item.type}>

            <span>{item.type}</span>

            <span>{item.total}</span>

            <span>{item.verified}</span>

            <span
              className={
                item.status === "Verified"
                  ? "status verified"
                  : "status review"
              }
            >
              {item.status}
            </span>

          </div>
        ))}

      </div>

    </div>
  );
}

export default PropertyInsights;