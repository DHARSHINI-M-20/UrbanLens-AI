export const API_MODE = (import.meta.env.VITE_API_MODE as string | undefined)?.toLowerCase() === "aws" ? "aws" : "local";
const configuredApiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "");
const apiBase = API_MODE === "aws" ? configuredApiBase ?? "" : configuredApiBase ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (API_MODE === "aws" && !apiBase) {
    throw new Error("VITE_API_BASE_URL must be set when VITE_API_MODE=aws.");
  }
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
  mode: API_MODE,
  demoStatus: () => request<Record<string, unknown>>("/demo/status"),
  seedDemo: () => API_MODE === "aws" ? Promise.reject(new Error("Demo seeding is local-only.")) : request<Record<string, unknown>>("/demo/seed?confirm=true", { method: "POST" }),
  processDemo: () => API_MODE === "aws" ? Promise.reject(new Error("Demo processing is invoked through the controlled AWS pipeline.")) : request<Record<string, unknown>>("/demo/process", { method: "POST" }),
  resetDemo: () => API_MODE === "aws" ? Promise.reject(new Error("Cloud data is read-only from this dashboard.")) : request<Record<string, unknown>>("/demo/reset?confirm=true", { method: "DELETE" }),
  awsStatus: () => request<Record<string, unknown>>("/aws/status"),
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
  runs: async (id: string) => {
    try {
      return await request<Record<string, unknown>[]>(`/demo/runs${encodedDataset(id)}`);
    } catch {
      // Older deployed cloud APIs expose persisted processing metrics but not the run adapter route yet.
      const metrics = await request<Record<string, unknown>[]>(`/metrics${encodedDataset(id)}`);
      return metrics.map((metric) => ({
        run_id: metric.processing_id ?? metric.view_id,
        dataset_id: id,
        status: "simulated",
        simulation: true,
        started_at: metric.timestamp,
        completed_at: metric.timestamp,
        processed_views: 1,
        metrics: metric,
        provenance: metric.provenance ?? "Simulated cloud processing metrics",
      }));
    }
  },
  challengeQuery: async (name: string, id: string) => {
    const response = await request<Record<string, unknown> | Record<string, unknown>[]>(`/queries/${name}${encodedDataset(id)}`);
    if (Array.isArray(response)) {
      const records = response.map((item) => ({ ...item }));
      const isFixedDemo = id === "tn_study_area_demo_v1";
      return {
        query_name: name,
        dataset_id: id,
        simulation: isFixedDemo,
        result_count: records.length,
        generated_at: null,
        run_id: null,
        records,
        provenance: records[0]?.provenance ?? (isFixedDemo
          ? "SYNTHETIC DEMONSTRATION DATA — NOT REAL STREET VIEW DATA"
          : "Provenance unavailable from this legacy response."),
        limitations: ["Legacy raw-array response: the frontend does not apply query filtering or infer completeness; results and provenance were not fully described by the API."],
      };
    }
    const records = Array.isArray(response.records) ? response.records as Record<string, unknown>[] :
      response.by_street && typeof response.by_street === "object" ? Object.values(response.by_street as Record<string, Record<string, unknown>[]>).flat() : [];
    const allVlmRun = response.all_vlm_run_performed === true;
    const hypothetical = (response.hypothetical_all_vlm_estimate ?? response.workflow_cost_comparison ?? {}) as Record<string, unknown>;
    return {
      ...response,
      query_name: response.query_name ?? name,
      dataset_id: response.dataset_id ?? id,
      simulation: response.simulation ?? id === "tn_study_area_demo_v1",
      result_count: response.result_count ?? records.length,
      generated_at: response.generated_at ?? null,
      run_id: response.run_id ?? null,
      records,
      provenance: response.provenance ?? (id === "tn_study_area_demo_v1"
        ? "SYNTHETIC DEMONSTRATION DATA — NOT REAL STREET VIEW DATA"
        : "Provenance unavailable from this legacy response."),
      limitations: response.limitations ?? ["Response normalized from a legacy API; some provenance fields may be unavailable."],
      ...(name === "routed-vs-all-vlm" ? {
        measured_routed_metrics: response.measured_routed_metrics ?? response.processing_route_distribution ?? {},
        hypothetical_all_vlm_estimate: { ...hypothetical, status: allVlmRun ? "RUN_REPORTED" : "NOT_RUN" },
        all_vlm_run_performed: allVlmRun,
        all_vlm_status: response.all_vlm_status ?? (allVlmRun ? "RUN_REPORTED" : "NOT_RUN"),
        quality_comparison_status: response.quality_comparison_status ?? "NOT_EVALUABLE",
        cost_status: response.cost_status ?? hypothetical.cost_status ?? "unavailable",
      } : {}),
    };
  },
  reviewDecision: (reviewId: string, status: string, reviewer: string, decision?: string,
    correctedAttributes?: Record<string, unknown>, reviewerNote?: string) =>
    API_MODE === "aws" ? Promise.reject(new Error("Cloud review records are read-only from this dashboard.")) : request<Record<string, unknown>>(`/reviews/${encodeURIComponent(reviewId)}/decision`, {
      method: "PATCH",
      body: JSON.stringify({ status, reviewer, reviewer_decision: decision ?? status,
        corrected_attributes: correctedAttributes ?? {}, reviewer_note: reviewerNote ?? null }),
    }),
};
