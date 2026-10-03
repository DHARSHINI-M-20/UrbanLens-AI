export type Status =
  | "MATCHED"
  | "PARTIAL"
  | "UNMATCHED"
  | "LOW CONFIDENCE"
  | "NOT VERIFIED"
  | "MISMATCH";

export type BuildingType =
  | "Residential"
  | "Commercial"
  | "Mixed-use"
  | "Institutional";

export type AssetType = string;

export interface KPIData {
  title: string;
  value: string | number;
  change: string;
  description: string;
  icon: string;
  type: "positive" | "negative" | "neutral";
}

export interface Building {
  id: string;
  street: string;
  latitude: number | null;
  longitude: number | null;
  type: BuildingType | string;
  floors: number | null;
  floorStatus?: "known" | "unknown" | "not_detected" | "unavailable";
  confidence: number | null;
  ocr: string;
  matchedProperty: string;
  matchScore: number | null;
  status: Status;
  buildingType?: BuildingType;
  processing?: string;
  observationId?: string;
  assetType?: string;
  attributes?: Record<string, unknown>;
  positionConfidence?: number | null;
  positionMethod?: string;
  sourceViewId?: string;
  heading?: number | null;
  fieldOfView?: number | null;
  modelRoute?: string;
  matchStatus?: string;
  discrepancy?: string;
  reviewStatus?: string;
  provenance?: string;
  simulation?: boolean;
  rawRecord?: Record<string, unknown>;
  streetId?: string;
}

export type ReviewAction = "pending" | "confirmed" | "rejected" | "corrected";

export interface ReviewItem {
  id: string;
  title: string;
  description: string;
  priority: "High" | "Medium" | "Low";
  confidence: number | null;
  buildingId?: string;
  detail?: string;
  reviewId?: string;
  observationId?: string;
  status?: string;
  rawRecord?: Record<string, unknown>;
}

export interface Asset {
  id: string;
  type: AssetType;
  street: string;
  latitude: number | null;
  longitude: number | null;
  confidence: number | null;
  status: Status;
}

export interface AnalysisRecord {
  id: string;
  location: string;
  date: string;
  buildings: number;
  assets: number;
  status: "Completed" | "Processing" | "Review";
  confidence: number;
}

export interface ChartData {
  name: string;
  value: number;
}

export interface FilterState {
  status: string;
  buildingType: string;
  confidence: string;
}
