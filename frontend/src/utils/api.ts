const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

const encodedDataset = (datasetId: string) => `?dataset_id=${encodeURIComponent(datasetId)}`;

export const api = {
  demoStatus: () => request<Record<string, unknown>>("/demo/status"),
  seedDemo: () => request<Record<string, unknown>>("/demo/seed", { method: "POST" }),
  processDemo: () => request<Record<string, unknown>>("/demo/process", { method: "POST" }),
  resetDemo: () => request<Record<string, unknown>>("/demo/reset", { method: "DELETE" }),
  studyArea: () => request<{ metadata: Record<string, unknown>; geojson: GeoJSON.FeatureCollection }>("/study-area"),
  streets: (id: string) => request<Record<string, unknown>[]>(`/streets${encodedDataset(id)}`),
  samples: (id: string) => request<Record<string, unknown>[]>(`/sampling/points${encodedDataset(id)}`),
  panoramas: (id: string) => request<Record<string, unknown>[]>(`/panoramas${encodedDataset(id)}`),
  views: (id: string) => request<Record<string, unknown>[]>(`/views${encodedDataset(id)}`),
  observations: (id: string) => request<Record<string, unknown>[]>(`/observations${encodedDataset(id)}`),
  ocr: (id: string) => request<Record<string, unknown>[]>(`/observations/ocr${encodedDataset(id)}`),
  references: (id: string) => request<Record<string, unknown>[]>(`/references${encodedDataset(id)}`),
  matches: (id: string) => request<Record<string, unknown>[]>(`/matching${encodedDataset(id)}`),
  discrepancies: (id: string) => request<Record<string, unknown>[]>(`/discrepancies${encodedDataset(id)}`),
  reviews: (id: string) => request<Record<string, unknown>[]>(`/reviews${encodedDataset(id)}`),
  metrics: (id: string) => request<Record<string, unknown>[]>(`/metrics${encodedDataset(id)}`),
  metricsSummary: (id: string) => request<Record<string, unknown>>(`/metrics/summary${encodedDataset(id)}`),
  analytics: (id: string) => request<Record<string, unknown>>(`/analytics/summary${encodedDataset(id)}`),
  reviewDecision: (reviewId: string, status: string, reviewer: string, decision?: string) =>
    request<Record<string, unknown>>(`/reviews/${encodeURIComponent(reviewId)}/decision`, {
      method: "PATCH",
      body: JSON.stringify({ status, reviewer, reviewer_decision: decision ?? status }),
    }),
};
