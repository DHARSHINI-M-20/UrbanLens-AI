import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { API_MODE, api } from "../utils/api";
import { nullableCoordinate, nullableNumber, nullablePercent } from "../utils/recordValues";
import type { Asset, Building, ReviewItem } from "../types";

export const DEMO_DATASET_ID = "tn_study_area_demo_v1";
export const DEMO_BANNER = "SYNTHETIC DEMONSTRATION DATA — NOT REAL STREET VIEW DATA\nGenerated within the official FarmwiseAI study-area boundary.\nGenerated observations and references are not an official property register.";

type RecordData = Record<string, unknown>;

interface DashboardContextValue {
  apiMode: "local" | "aws";
  awsStatus: RecordData | null;
  seeded: boolean;
  loading: boolean;
  busy: boolean;
  error: string | null;
  statusMessage: string | null;
  summary: RecordData | null;
  studyArea: GeoJSON.FeatureCollection | null;
  studyAreaMetadata: Record<string, unknown> | null;
  streets: RecordData[];
  samplingPoints: RecordData[];
  observations: RecordData[];
  ocr: RecordData[];
  references: RecordData[];
  discrepancyRecords: RecordData[];
  reviews: ReviewItem[];
  metrics: RecordData[];
  runs: RecordData[];
  buildings: Building[];
  filteredBuildings: Building[];
  discrepancies: Building[];
  assets: Asset[];
  search: string;
  setSearch: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  buildingTypeFilter: string;
  setBuildingTypeFilter: (value: string) => void;
  confidenceFilter: string;
  setConfidenceFilter: (value: string) => void;
  selectedStreet: string;
  setSelectedStreet: (value: string) => void;
  selectedBuilding: Building | null;
  isDrawerOpen: boolean;
  selectBuilding: (building: Building) => void;
  closeDrawer: () => void;
  refresh: () => Promise<void>;
  seedDemo: () => Promise<void>;
  processDemo: () => Promise<void>;
  resetDemo: () => Promise<void>;
  decideReview: (item: ReviewItem, decision: "approved" | "rejected", reviewerDecision?: string,
    correctedAttributes?: Record<string, unknown>, reviewerNote?: string) => Promise<void>;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

function asText(value: unknown, fallback = "") {
  return value == null ? fallback : String(value);
}

function mapObservation(record: RecordData, streetNames: Map<string, string>): Building {
  const attributes = (record.attributes ?? {}) as RecordData;
  const positioning = (record.positioning ?? {}) as RecordData;
  const match = (record.match_record ?? {}) as RecordData;
  const matchStatus = asText(record.match_status ?? match.match_status, "unknown").toLowerCase();
  const confidence = nullablePercent(record.confidence);
  const status = matchStatus === "matched" ? "MATCHED" : matchStatus === "mismatch" ? "MISMATCH" :
    matchStatus === "possible_match" ? "PARTIAL" : confidence != null && confidence < 70 ? "LOW CONFIDENCE" :
      matchStatus === "unmatched" ? "UNMATCHED" : "NOT VERIFIED";
  const rawType = asText(record.asset_type, "other");
  const use = asText(attributes.building_use, "unknown");
  const normalizedUse = use.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const coordinates = positioning.latitude != null && positioning.longitude != null ? positioning : record;
  const parsedFloors = nullableNumber(attributes.visible_floor_count);
  const floors = parsedFloors != null && Number.isInteger(parsedFloors) && parsedFloors >= 0 ? parsedFloors : null;
  const positionConfidence = nullableNumber(positioning.positioning_confidence);
  const signText = attributes.visible_sign_text;
  const ocr = Array.isArray(signText) ? signText.join(" / ") : asText(signText, asText(record.ocr_text, "OCR unavailable"));
  return {
    id: asText(record.observation_id),
    observationId: asText(record.observation_id),
    street: streetNames.get(asText(record.street_id)) ?? asText(record.street_id, "Unassigned simulated street"),
    latitude: nullableCoordinate(coordinates.latitude, 90),
    longitude: nullableCoordinate(coordinates.longitude, 180),
    type: normalizedUse,
    buildingType: normalizedUse as Building["buildingType"],
    assetType: rawType,
    floors,
    floorStatus: attributes.floor_count_status === "unavailable" ? "unavailable"
      : Object.prototype.hasOwnProperty.call(attributes, "visible_floor_count")
        ? floors == null ? "unknown" : "known" : "not_detected",
    confidence,
    ocr,
    matchedProperty: asText(record.reference_id,
      matchStatus === "unmatched" ? "No match in supplied references" : "Reference match unavailable"),
    matchScore: nullablePercent(match.match_score),
    status,
    processing: asText(record.model_route, "local_model"),
    attributes,
    streetId: asText(record.street_id),
    positionConfidence: positionConfidence != null && positionConfidence >= 0 && positionConfidence <= 1 ? positionConfidence : null,
    positionMethod: asText(positioning.positioning_method, "not_positioned"),
    sourceViewId: asText(record.source_view_id),
    heading: nullableNumber(record.heading),
    fieldOfView: nullableNumber(record.field_of_view),
    modelRoute: asText(record.model_route, "small_model"),
    matchStatus,
    discrepancy: "",
    reviewStatus: asText(record.review_status, "pending"),
    provenance: asText(record.provenance, DEMO_BANNER),
    simulation: Boolean(record.simulation),
    rawRecord: record,
  };
}

function confidenceBucket(value: number | null) {
  if (value == null) return "Unknown";
  if (value >= 80) return "High";
  if (value >= 70) return "Medium";
  return "Low";
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [seeded, setSeeded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<RecordData | null>(null);
  const [awsStatus, setAwsStatus] = useState<RecordData | null>(null);
  const [studyArea, setStudyArea] = useState<GeoJSON.FeatureCollection | null>(null);
  const [studyAreaMetadata, setStudyAreaMetadata] = useState<Record<string, unknown> | null>(null);
  const [streets, setStreets] = useState<RecordData[]>([]);
  const [samplingPoints, setSamplingPoints] = useState<RecordData[]>([]);
  const [observations, setObservations] = useState<RecordData[]>([]);
  const [ocr, setOcr] = useState<RecordData[]>([]);
  const [references, setReferences] = useState<RecordData[]>([]);
  const [discrepancyRecords, setDiscrepancyRecords] = useState<RecordData[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [metrics, setMetrics] = useState<RecordData[]>([]);
  const [runs, setRuns] = useState<RecordData[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [buildingTypeFilter, setBuildingTypeFilter] = useState("All");
  const [confidenceFilter, setConfidenceFilter] = useState("All");
  const [selectedStreet, setSelectedStreet] = useState("All");
  const [selectedBuilding, setSelectedBuilding] = useState<Building | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [status, area, nextAwsStatus] = await Promise.all([
        api.demoStatus(),
        api.studyArea(),
        API_MODE === "aws" ? api.awsStatus() : Promise.resolve(null),
      ]);
      setAwsStatus(nextAwsStatus);
      setStudyArea(area.geojson);
      setStudyAreaMetadata(area.metadata);
      const isSeeded = Boolean(status.seeded);
      setSeeded(isSeeded);
      if (!isSeeded) {
        setSummary(null);
        setStreets([]); setSamplingPoints([]); setObservations([]); setOcr([]);
        setReferences([]); setDiscrepancyRecords([]); setReviews([]); setMetrics([]); setRuns([]);
        return;
      }
      const [nextStreets, nextSamples, nextObservations, nextOcr, nextReferences,
        nextDiscrepancies, nextReviews, nextMetrics, nextSummary, nextRuns] = await Promise.all([
        api.streets(DEMO_DATASET_ID), api.samples(DEMO_DATASET_ID),
        api.observations(DEMO_DATASET_ID), api.ocr(DEMO_DATASET_ID), api.references(DEMO_DATASET_ID),
        api.discrepancies(DEMO_DATASET_ID), api.reviews(DEMO_DATASET_ID),
        api.metrics(DEMO_DATASET_ID), api.analytics(DEMO_DATASET_ID), api.runs(DEMO_DATASET_ID),
      ]);
      setStreets(nextStreets); setSamplingPoints(nextSamples);
      setObservations(nextObservations); setOcr(nextOcr); setReferences(nextReferences);
      setDiscrepancyRecords(nextDiscrepancies);
      setReviews(nextReviews.map((item) => {
        const observation = nextObservations.find((record) => record.observation_id === item.observation_id) ?? {};
        const relatedDiscrepancy = nextDiscrepancies.find((record) => record.observation_id === item.observation_id) ?? {};
        const matchedReference = nextReferences.find((record) => record.reference_id === observation.reference_id) ?? {};
        const reviewStatus = item.status === "approved" && item.reviewer_decision === "corrected" ? "corrected" : asText(item.status, "pending");
        return {
        id: asText(item.review_id), reviewId: asText(item.review_id), observationId: asText(item.observation_id),
        title: asText(item.reason, "Observation review"), description: asText(item.provenance, DEMO_BANNER),
        priority: asText(item.priority, "medium").replace(/^./, (c) => c.toUpperCase()) as ReviewItem["priority"],
        confidence: nullablePercent(item.confidence), status: reviewStatus,
        detail: `${asText(observation.asset_type, "unknown asset")} · OCR: ${asText(observation.ocr_text, "see evidence")}`,
        rawRecord: { ...item, observation, discrepancy: relatedDiscrepancy, reference: matchedReference },
      };
      }));
      setMetrics(nextMetrics); setSummary(nextSummary); setRuns(nextRuns);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load the UrbanLens API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function perform(action: () => Promise<unknown>, message: string) {
    setBusy(true); setError(null); setStatusMessage(null);
    try {
      await action();
      await refresh();
      setStatusMessage(message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The requested API action failed.");
    } finally {
      setBusy(false);
    }
  }

  const streetNames = new Map(streets.map((street) => [asText(street.street_id), asText(street.name)]));
  const buildings = observations.map((record) => {
    const building = mapObservation(record, streetNames);
    const discrepancy = discrepancyRecords.find((item) => item.observation_id === building.id);
    const review = reviews.find((item) => item.observationId === building.id);
    return {
      ...building,
      discrepancy: asText(discrepancy?.description),
      reviewStatus: review?.status ?? building.reviewStatus,
    };
  });
  const filteredBuildings = buildings.filter((building) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || `${building.id} ${building.street} ${building.streetId} ${building.ocr} ${building.assetType} ${building.modelRoute} ${building.matchStatus} ${String(building.attributes?.building_use ?? "")}`.toLowerCase().includes(query);
    const matchesStatus = statusFilter === "All" || building.status === statusFilter;
    const matchesType = buildingTypeFilter === "All" || building.buildingType === buildingTypeFilter;
    const matchesConfidence = confidenceFilter === "All" || confidenceBucket(building.confidence) === confidenceFilter;
    const matchesStreet = selectedStreet === "All" || building.streetId === selectedStreet;
    return matchesSearch && matchesStatus && matchesType && matchesConfidence && matchesStreet;
  });
  const discrepancyIds = new Set(discrepancyRecords.map((item) => asText(item.observation_id)).filter(Boolean));
  const discrepancies = filteredBuildings.filter((building) => discrepancyIds.has(building.id) || building.status !== "MATCHED");
  const assetLabel = (value: string) => value.split(/[_\s-]+/).filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
  const assets: Asset[] = buildings.filter((building) => building.assetType !== "building").map((building) => ({
    id: building.id,
    type: assetLabel(building.assetType ?? "other"),
    street: building.street, confidence: building.confidence, latitude: building.latitude,
    longitude: building.longitude, status: building.status,
  }));

  const value: DashboardContextValue = {
    apiMode: API_MODE,
    awsStatus,
    seeded, loading, busy, error, statusMessage, summary, studyArea, streets,
    observations, ocr, references, discrepancyRecords, reviews, metrics, runs,
    studyAreaMetadata, samplingPoints,
    buildings, filteredBuildings, discrepancies, assets, search, setSearch, statusFilter, setStatusFilter,
    buildingTypeFilter, setBuildingTypeFilter, confidenceFilter, setConfidenceFilter,
    selectedStreet, setSelectedStreet,
    selectedBuilding, isDrawerOpen,
    selectBuilding: (building) => { setSelectedBuilding(building); setIsDrawerOpen(true); },
    closeDrawer: () => setIsDrawerOpen(false),
    refresh,
    seedDemo: () => perform(api.seedDemo, "Simulated dataset seeded and processed."),
    processDemo: () => perform(api.processDemo, "Simulated views processed through the backend pipeline."),
    resetDemo: () => perform(api.resetDemo, "Only the scoped simulated dataset was reset."),
    decideReview: async (item, decision, reviewerDecision, correctedAttributes, reviewerNote) => perform(
      () => api.reviewDecision(item.reviewId ?? item.id, decision, "demo-reviewer", reviewerDecision,
        correctedAttributes, reviewerNote),
      `Review marked ${decision}.`,
    ),
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) throw new Error("useDashboard must be used within DashboardProvider");
  return context;
}
