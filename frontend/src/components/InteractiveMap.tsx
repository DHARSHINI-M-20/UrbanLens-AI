import { useEffect, useState } from "react";

import {
  MapContainer,
  Marker,
  Popup,
  GeoJSON,
  CircleMarker,
  useMap,
} from "react-leaflet";

import L from "leaflet";

import { Building2, Lightbulb, Zap } from "lucide-react";

import type { Asset, Building, Status } from "../types";
import { hasCoordinates, nullableCoordinate } from "../utils/recordValues";

import MapLegend from "./MapLegend";
import MapControls from "./MapControls";

import "leaflet/dist/leaflet.css";

// react-leaflet 5 type definitions can be overly restrictive with the current React/TS toolchain.
// The runtime components are still the official react-leaflet components.
/* eslint-disable @typescript-eslint/no-explicit-any */
const SafeMapContainer = MapContainer as any;
const SafeMarker = Marker as any;
/* eslint-enable @typescript-eslint/no-explicit-any */

interface InteractiveMapProps {
  buildings: Building[];
  streets: Record<string, unknown>[];
  samplingPoints: Record<string, unknown>[];
  studyArea: GeoJSON.FeatureCollection | null;
  onBuildingSelect?: (building: Building) => void;
}

function hasUsableLocation<T extends { latitude: number | null; longitude: number | null }>(
  record: T,
): record is T & { latitude: number; longitude: number } {
  return hasCoordinates(record.latitude, record.longitude);
}

function validCoordinate(latitude: unknown, longitude: unknown): latitude is number {
  return typeof latitude === "number" && typeof longitude === "number"
    && hasCoordinates(latitude, longitude);
}

const statusColors: Record<Status, string> = {
  MATCHED: "#22c55e",
  PARTIAL: "#f59e0b",
  MISMATCH: "#fb7185",
  UNMATCHED: "#ef4444",
  "LOW CONFIDENCE": "#f97316",
  "NOT VERIFIED": "#94a3b8",
};

function createBuildingIcon(status: Status) {
  const color = statusColors[status];
  return L.divIcon({
    className: "urban-building-marker",
    html: `
      <div class="building-marker" style="--marker-color: ${color}; border-color: ${color};">
        <div class="building-marker-icon">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 21h18"/><path d="M6 21V5l6-3v19"/><path d="M18 21V9l-6-3"/>
            <path d="M9 9h1"/><path d="M9 13h1"/><path d="M9 17h1"/><path d="M15 12h1"/><path d="M15 16h1"/>
          </svg>
        </div>
      </div>`,
    iconSize: [42, 42],
    iconAnchor: [21, 21],
    popupAnchor: [0, -22],
  });
}

function createAssetIcon(asset: Asset) {
  const color = statusColors[asset.status];
  const icon =
    asset.type === "Streetlight"
      ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21h6"/><path d="M12 17v4"/><path d="M7 8h10"/><path d="M8 8a4 4 0 0 1 8 0"/><path d="M12 4v4"/></svg>`
      : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"/><path d="M7 6h10"/><path d="M6 12h12"/><path d="M5 18h14"/></svg>`;

  return L.divIcon({
    className: "urban-asset-marker",
    html: `<div class="asset-marker" style="--marker-color: ${color}; border-color: ${color};">${icon}</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -18],
  });
}

function getStatusClass(status: Status) {
  switch (status) {
    case "MATCHED": return "matched";
    case "PARTIAL": return "partial";
    case "MISMATCH": return "unmatched";
    case "UNMATCHED": return "unmatched";
    case "LOW CONFIDENCE": return "low";
    case "NOT VERIFIED": return "not-verified";
    default: return "";
  }
}

function MapReadyBinder({ onReady }: { onReady: (map: L.Map) => void }) {
  const map = useMap();
  useEffect(() => {
    onReady(map);
  }, [map, onReady]);
  return null;
}

function BuildingPopup({ building }: { building: Building }) {
  return (
    <div className="map-popup">
      <div className="popup-header">
        <div>
          <span className="popup-label">BUILDING</span>
          <h4>{building.id}</h4>
        </div>
        <span className={`popup-status ${getStatusClass(building.status)}`}>{building.status}</span>
      </div>
      <div className="popup-divider" />
      <div className="popup-info">
        <div><span>Street</span><strong>{building.street}</strong></div>
        <div><span>Building Type</span><strong>{building.type}</strong></div>
        <div><span>Floors</span><strong>{building.floors == null ? (building.floorStatus === "unknown" ? "Unknown" : "Not detected") : building.floors}</strong></div>
        <div><span>Confidence</span><strong>{building.confidence == null ? "Unavailable" : `${building.confidence}%`}</strong></div>
        <div><span>OCR</span><strong>{building.ocr || "No text detected"}</strong></div>
        <div><span>Match Score</span><strong>{building.matchScore == null ? "Unavailable" : `${building.matchScore}%`}</strong></div>
      </div>
      <div className="popup-footer">
        {hasUsableLocation(building) ? `${building.latitude.toFixed(4)}, ${building.longitude.toFixed(4)}` : "Location unavailable"}
      </div>
    </div>
  );
}

function AssetPopup({ asset }: { asset: Asset }) {
  return (
    <div className="map-popup asset-popup">
      <div className="popup-header">
        <div>
          <span className="popup-label">ASSET</span>
          <h4>{asset.id}</h4>
        </div>
        <span className={`popup-status ${getStatusClass(asset.status)}`}>{asset.status}</span>
      </div>
      <div className="popup-divider" />
      <div className="popup-info">
        <div><span>Asset Type</span><strong>{asset.type}</strong></div>
        <div><span>Street</span><strong>{asset.street}</strong></div>
        <div><span>Confidence</span><strong>{asset.confidence == null ? "Unavailable" : `${asset.confidence}%`}</strong></div>
      </div>
    </div>
  );
}

function centerFromStudyArea(studyArea: GeoJSON.FeatureCollection | null): [number, number] | null {
  const positions: number[][] = [];
  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      positions.push(value as number[]);
      return;
    }
    value.forEach(visit);
  };
  studyArea?.features.forEach((feature) => {
    if (!feature.geometry) return;
    if (feature.geometry.type === "GeometryCollection") visit(feature.geometry.geometries);
    else visit(feature.geometry.coordinates);
  });
  if (!positions.length) return null;
  const longitudes = positions.map(([longitude]) => longitude);
  const latitudes = positions.map(([, latitude]) => latitude);
  return [(Math.min(...latitudes) + Math.max(...latitudes)) / 2,
    (Math.min(...longitudes) + Math.max(...longitudes)) / 2];
}

export default function InteractiveMap({ buildings, streets, samplingPoints, studyArea, onBuildingSelect }: InteractiveMapProps) {
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [tileStyle, setTileStyle] = useState<"standard" | "dark">("dark");
  const mapCenter = centerFromStudyArea(studyArea);
  const buildingRecords = buildings.filter((record) => record.assetType === "building");
  const assetRecords = buildings.filter((record) => record.assetType && record.assetType !== "building");

  return (
    <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[10px] font-extrabold tracking-widest text-cyan-400">GEOSPATIAL INTELLIGENCE</div>
          <h3 className="m-0 mt-1 text-lg font-bold text-white">Interactive Street Intelligence</h3>
          <p className="m-0 mt-1 text-xs text-slate-500">Explore persisted building and asset observations; seeded records are synthetic.</p>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            <Building2 size={15} className="text-indigo-400" /> {buildingRecords.length} Buildings
          </div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            <Lightbulb size={15} className="text-amber-400" /> {assetRecords.filter((a) => a.assetType === "streetlight").length} Streetlights
          </div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            <Zap size={15} className="text-violet-400" /> {assetRecords.filter((a) => a.assetType === "electric_pole").length} Poles
          </div>
        </div>
      </div>

      {!mapCenter && <p role="status" className="mb-3 rounded-lg border border-amber-300/20 p-3 text-xs text-amber-100">Map unavailable: official study-area geometry is not loaded.</p>}
      {buildings.some((record) => !hasCoordinates(record.latitude, record.longitude)) &&
        <p className="mb-3 text-xs text-slate-400">Some observations have no usable location and are not shown as map markers.</p>}
      {mapCenter && <div className={`relative h-[620px] overflow-hidden rounded-2xl ${tileStyle === "dark" ? "map-theme-dark" : "map-theme-standard"}`}>
        <SafeMapContainer
          center={mapCenter}
          zoom={15}
          minZoom={12}
          maxZoom={19}
          scrollWheelZoom={true}
          zoomControl={false}
          className="urban-map"
        >
          <MapReadyBinder onReady={setMapInstance} />

          {studyArea && <GeoJSON data={studyArea} style={{ color: "#22d3ee", weight: 2, fillOpacity: 0.04 }} />}
          {streets.map((street) => {
            const geometry = street.geometry as GeoJSON.Geometry | undefined;
            if (!geometry) return null;
            const feature: GeoJSON.Feature = {
              type: "Feature", geometry, properties: { name: street.name, street_id: street.street_id },
            };
            return <GeoJSON key={String(street.street_id)} data={feature}
              style={{ color: "#fbbf24", weight: 4, opacity: 0.9 }} />;
          })}
          {samplingPoints.map((sample) => {
            const latitude = nullableCoordinate(sample.latitude, 90);
            const longitude = nullableCoordinate(sample.longitude, 180);
            if (latitude === null || longitude === null || !validCoordinate(latitude, longitude)) return null;
            return <CircleMarker key={String(sample.sample_id)} center={[latitude, longitude]} radius={3}
              pathOptions={{ color: "#f8fafc", fillColor: "#38bdf8", fillOpacity: 0.8 }}>
              <Popup>Simulated sampling point · {String(sample.status ?? "pending")}</Popup>
            </CircleMarker>;
          })}

          {buildingRecords
            .filter(hasUsableLocation)
            .map((building) => (
              <SafeMarker
                key={building.id}
                position={[building.latitude, building.longitude]}
                icon={createBuildingIcon(building.status)}
                eventHandlers={{ click: () => onBuildingSelect?.(building) }}
              >
                <Popup>
                  <BuildingPopup building={building} />
                  <button className="popup-view-button" onClick={() => onBuildingSelect?.(building)}>
                    View Evidence →
                  </button>
                </Popup>
              </SafeMarker>
            ))}

          {assetRecords
            .filter(hasUsableLocation)
            .map((record) => ({
              id: record.id,
              type: record.assetType === "electric_pole" ? "Electric Pole" : record.assetType === "streetlight" ? "Streetlight" : record.assetType ?? "Asset",
              street: record.street,
              confidence: record.confidence,
              latitude: record.latitude,
              longitude: record.longitude,
              status: record.status,
              record,
            } as Asset & { record: Building }))
            .map((asset) => (
              <SafeMarker key={asset.id} position={[asset.latitude, asset.longitude]} icon={createAssetIcon(asset)}>
                <Popup>
                  <AssetPopup asset={asset} />
                  <button className="popup-view-button" onClick={() => onBuildingSelect?.(asset.record)}>
                    View Evidence
                  </button>
                </Popup>
              </SafeMarker>
            ))}
        </SafeMapContainer>

        <MapControls
          map={mapInstance}
          center={mapCenter}
          onToggleLayer={() => setTileStyle((s) => (s === "dark" ? "standard" : "dark"))}
        />

        <MapLegend />

        <div className="absolute bottom-4 left-4 z-[400] flex items-center gap-2.5 rounded-xl border border-white/10 bg-[#0f172a]/90 px-3.5 py-2.5 backdrop-blur-md">
          <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
          <div>
          <strong className="block text-[11px] font-bold text-white">Persisted Demo Observations</strong>
            <span className="block text-[10px] text-slate-500">
              {buildings.length} persisted observations
            </span>
          </div>
        </div>
      </div>}
    </div>
  );
}
