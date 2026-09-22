import {
  Building2,
  Lightbulb,
  Zap,
  MapPin,
} from "lucide-react";

const buildings = [
  {
    id: "BLD_001",
    x: "25%",
    y: "28%",
    status: "MATCHED",
  },
  {
    id: "BLD_002",
    x: "48%",
    y: "38%",
    status: "PARTIAL",
  },
  {
    id: "BLD_003",
    x: "70%",
    y: "25%",
    status: "UNMATCHED",
  },
  {
    id: "BLD_004",
    x: "38%",
    y: "65%",
    status: "MATCHED",
  },
  {
    id: "BLD_005",
    x: "75%",
    y: "68%",
    status: "LOW CONFIDENCE",
  },
];

export default function MapView() {
  return (
    <div className="map-card">
      <div className="map-header">
        <div>
          <h3>Interactive Map</h3>
          <p>Buildings and infrastructure assets</p>
        </div>

        <div className="map-controls">
          <button className="map-control active">All</button>
          <button className="map-control">Buildings</button>
          <button className="map-control">Assets</button>
        </div>
      </div>

      <div className="map-area">

        <div className="road road-1"></div>
        <div className="road road-2"></div>
        <div className="road road-3"></div>

        {buildings.map((building) => (
          <div
            key={building.id}
            className={`building-marker ${building.status
              .toLowerCase()
              .replace(" ", "-")}`}
            style={{
              left: building.x,
              top: building.y,
            }}
            title={building.id}
          >
            <Building2 size={18} />
          </div>
        ))}

        <div className="asset-marker streetlight" style={{ left: "18%", top: "55%" }}>
          <Lightbulb size={15} />
        </div>

        <div className="asset-marker pole" style={{ left: "57%", top: "20%" }}>
          <Zap size={15} />
        </div>

        <div className="asset-marker streetlight" style={{ left: "85%", top: "48%" }}>
          <Lightbulb size={15} />
        </div>

        <div className="map-label">
          <MapPin size={15} />
          Urban Analysis Area
        </div>

        <div className="map-legend">
          <div>
            <span className="legend-dot matched"></span>
            Matched
          </div>

          <div>
            <span className="legend-dot partial"></span>
            Partial
          </div>

          <div>
            <span className="legend-dot unmatched"></span>
            Unmatched
          </div>

          <div>
            <span className="legend-dot low-confidence"></span>
            Low Confidence
          </div>
        </div>

      </div>
    </div>
  );
}