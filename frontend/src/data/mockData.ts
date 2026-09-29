import type { Asset, Building } from "../types";

export const buildings: Building[] = [
  {
    id: "BLD_001",
    street: "Anna Nagar Main Road",
    type: "Commercial",
    buildingType: "Commercial",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 3,
    confidence: 87,
    status: "MATCHED",
    ocr: "ABC HARDWARE",
    matchScore: 91,
    matchedProperty: "P-1023",
    latitude: 10.9995,
    longitude: 78.1195,
  },
  {
    id: "BLD_002",
    street: "Gandhi Road",
    type: "Residential",
    buildingType: "Residential",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 2,
    confidence: 94,
    status: "MATCHED",
    ocr: "HOME",
    matchScore: 96,
    matchedProperty: "P-1024",
    latitude: 11.0005,
    longitude: 78.1205,
  },
  {
    id: "BLD_003",
    street: "Market Street",
    type: "Commercial",
    buildingType: "Commercial",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 4,
    confidence: 72,
    status: "PARTIAL",
    ocr: "SRI STORES",
    matchScore: 74,
    matchedProperty: "P-1025",
    latitude: 10.9985,
    longitude: 78.1215,
  },
  {
    id: "BLD_004",
    street: "Temple Road",
    type: "Institutional",
    buildingType: "Institutional",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 2,
    confidence: 61,
    status: "LOW CONFIDENCE",
    ocr: "SCHOOL",
    matchScore: 63,
    matchedProperty: "P-1026",
    latitude: 10.9975,
    longitude: 78.1185,
  },
  {
    id: "BLD_005",
    street: "Station Road",
    type: "Mixed-use",
    buildingType: "Mixed-use",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 3,
    confidence: 48,
    status: "UNMATCHED",
    ocr: "NO CLEAR TEXT",
    matchScore: 42,
    matchedProperty: "P-1027",
    latitude: 11.0015,
    longitude: 78.1175,
  },
  {
    id: "BLD_006",
    street: "College Road",
    type: "Residential",
    buildingType: "Residential",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 1,
    confidence: 91,
    status: "MATCHED",
    ocr: "HOUSE 24",
    matchScore: 89,
    matchedProperty: "P-1028",
    latitude: 11.0025,
    longitude: 78.1195,
  },
  {
    id: "BLD_007",
    street: "Bus Stand Road",
    type: "Commercial",
    buildingType: "Commercial",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 4,
    confidence: 55,
    status: "NOT VERIFIED",
    ocr: "SHOP",
    matchScore: 51,
    matchedProperty: "P-1029",
    latitude: 10.9965,
    longitude: 78.1205,
  },
  {
    id: "BLD_008",
    street: "East Street",
    type: "Residential",
    buildingType: "Residential",
    processing: "CV → OCR → multi-view fusion → geo match",
    floors: 2,
    confidence: 82,
    status: "MATCHED",
    ocr: "RESIDENCE",
    matchScore: 85,
    matchedProperty: "P-1030",
    latitude: 10.9990,
    longitude: 78.1220,
  },
];

export const assets: Asset[] = [
  {
    id: "AST_001",
    type: "Streetlight",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 10.9992,
    longitude: 78.1192,
    status: "MATCHED",
  },
  {
    id: "AST_002",
    type: "Streetlight",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 11.0002,
    longitude: 78.1202,
    status: "MATCHED",
  },
  {
    id: "AST_003",
    type: "Streetlight",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 10.9982,
    longitude: 78.1212,
    status: "PARTIAL",
  },
  {
    id: "AST_004",
    type: "Electric Pole",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 10.9978,
    longitude: 78.1188,
    status: "MATCHED",
  },
  {
    id: "AST_005",
    type: "Electric Pole",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 11.0010,
    longitude: 78.1178,
    status: "LOW CONFIDENCE",
  },
  {
    id: "AST_006",
    type: "Electric Pole",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 11.0020,
    longitude: 78.1190,
    status: "UNMATCHED",
  },
  {
    id: "AST_007",
    type: "Traffic Signal",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 10.9968,
    longitude: 78.1200,
    status: "MATCHED",
  },
  {
    id: "AST_008",
    type: "Streetlight",
    street: "Study Area Corridor",
    confidence: 88,
    latitude: 11.0000,
    longitude: 78.1220,
    status: "NOT VERIFIED",
  },
];

export const buildingUseData = [
  { name: "Residential", value: 420 },
  { name: "Commercial", value: 315 },
  { name: "Mixed-use", value: 180 },
  { name: "Institutional", value: 120 },
];

export const floorDistributionData = [
  { name: "1 Floor", value: 210 },
  { name: "2 Floors", value: 380 },
  { name: "3 Floors", value: 290 },
  { name: "4+ Floors", value: 155 },
];

export const assetDistributionData = [
  { name: "Streetlights", value: 436 },
  { name: "Electric Poles", value: 318 },
  { name: "Traffic Signals", value: 48 },
  { name: "Sign Boards", value: 126 },
];

export const assetData = assetDistributionData;

export const matchingData = [
  { name: "Matched", value: 986 },
  { name: "Partial", value: 124 },
  { name: "Unmatched", value: 142 },
  { name: "Not Verified", value: 76 },
];

export const confidenceData = [
  { name: "High", value: 720 },
  { name: "Medium", value: 380 },
  { name: "Low", value: 228 },
];

export const aiRoutingData = [
  { name: "Lightweight", value: 82 },
  { name: "VLM", value: 18 },
];

export const discrepancyData = buildings
  .filter((building) => building.status !== "MATCHED")
  .map((building) => ({
    id: building.id,
    street: building.street,
    type: building.type,
    floors: building.floors,
    ocr: building.ocr,
    match: `${building.matchScore}%`,
    confidence: `${building.confidence}%`,
    status: building.status,
  }));

export const reviewItems: import("../types").ReviewItem[] = [
  { id: "FND_014", title: "Low-confidence building classification", description: "The model isolated an observation with limited visual evidence.", priority: "Medium", confidence: 61, buildingId: "BLD_004", detail: "Floor count: 2 / 3 uncertain" },
  { id: "FND_021", title: "OCR and property record mismatch", description: "Detected signage does not align strongly with the associated record.", priority: "High", confidence: 54, buildingId: "BLD_005", detail: "OCR read: \"NO CLEAR TEXT\"" },
  { id: "FND_027", title: "Infrastructure position variance", description: "A street asset is offset from the expected geospatial position.", priority: "Low", confidence: 68, buildingId: "AST_005", detail: "Pole offset ~4.2m from footprint" },
  { id: "FND_031", title: "Low-confidence floor count", description: "Escalated to VLM but confidence remained below threshold.", priority: "Medium", confidence: 48, buildingId: "BLD_007", detail: "Floor count: 3 / 4 uncertain" },
];

export const analysisHistory: import("../types").AnalysisRecord[] = [
  { id: "RUN_1042", location: "Anna Nagar Corridor", date: "2026-09-24", buildings: 214, assets: 118, status: "Completed", confidence: 91 },
  { id: "RUN_1041", location: "Market Street Segment", date: "2026-09-23", buildings: 168, assets: 94, status: "Completed", confidence: 88 },
  { id: "RUN_1040", location: "Station Road Corridor", date: "2026-09-23", buildings: 142, assets: 76, status: "Review", confidence: 73 },
  { id: "RUN_1039", location: "Temple Road Segment", date: "2026-09-22", buildings: 96, assets: 52, status: "Processing", confidence: 65 },
  { id: "RUN_1038", location: "College Road Corridor", date: "2026-09-21", buildings: 187, assets: 103, status: "Completed", confidence: 94 },
];
