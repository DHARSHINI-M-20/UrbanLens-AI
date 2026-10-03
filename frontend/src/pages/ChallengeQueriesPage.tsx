import { useState } from "react";
import { api } from "../utils/api";
import { DEMO_DATASET_ID, useDashboard } from "../context/DashboardContext";
import PaginationControls from "../components/PaginationControls";
import { paginate } from "../utils/pagination";

type QuerySpec = { key: string; endpoint: string; title: string; explanation: string; criteria: string };
const queries: QuerySpec[] = [
  { key: "commercial", endpoint: "buildings-over-2-floors-without-match", title: "Commercial buildings >2 floors without a matching record", explanation: "No match in the currently supplied reference dataset; this does not mean no official property record exists.", criteria: "Building · commercial use · known whole-number floor count greater than two · explicit unmatched status." },
  { key: "streetlight", endpoint: "streets-without-streetlights", title: "Expected streetlights without an observed match", explanation: "Reports stored expected-streetlight discrepancies only when declared reference coverage is complete.", criteria: "Expected in reference · complete coverage · stored discrepancy says not observed within 25 m. Incomplete/unknown coverage is excluded." },
  { key: "floors", endpoint: "low-confidence-floor-counts", title: "Low-confidence floor counts pending review", explanation: "Confidence below the configured threshold; confidence unavailable is excluded, not treated as zero.", criteria: "Known whole-number floor count · finite confidence below threshold · pending/needs-review status." },
  { key: "unmatched", endpoint: "unmatched-buildings-by-street", title: "Explicitly unmatched buildings by street", explanation: "Groups only records marked unmatched; missing/unknown match status is excluded.", criteria: "Building · explicit unmatched status · grouped by street identifier (or Unassigned)." },
  { key: "routing", endpoint: "routed-vs-all-vlm", title: "Routed workflow and all-VLM baseline status", explanation: "Shows stored routed metrics. No all-VLM baseline is fabricated or run by this query.", criteria: "Routed values are persisted measurements for this demo dataset. All-VLM quality/cost stay unavailable unless actually measured." },
];

function printable(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function ChallengeQueriesPage() {
  const { apiMode } = useDashboard();
  const [results, setResults] = useState<Record<string, Record<string, unknown>>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("");

  async function run(spec: QuerySpec) {
    setLoading((current) => ({ ...current, [spec.key]: true }));
    setErrors((current) => ({ ...current, [spec.key]: "" }));
    try {
      const response = await api.challengeQuery(spec.endpoint, DEMO_DATASET_ID);
      setResults((current) => ({ ...current, [spec.key]: response }));
    } catch (cause) {
      setErrors((current) => ({ ...current, [spec.key]: cause instanceof Error ? cause.message : "Query failed." }));
    } finally {
      setLoading((current) => ({ ...current, [spec.key]: false }));
    }
  }

  return <div>
    <header className="mb-5">
      <span className="text-[10px] font-bold tracking-widest text-cyan-400">TASK 5</span>
      <h1 className="m-0 mt-1 text-2xl font-extrabold text-white">Task 5 Challenge Queries</h1>
      <p className="m-0 mt-1 text-[13px] text-slate-400">Run the five Task 5 questions against the fixed demonstration dataset. Arbitrary dataset selection is not available in this dashboard.</p>
    </header>
    <div className="mb-4 rounded-xl border border-amber-300/30 bg-amber-200/[0.08] p-3 text-xs text-amber-100">
      <strong className="mr-2">SYNTHETIC DEMONSTRATION DATA — NOT REAL STREET VIEW</strong>
      {apiMode === "aws" ? "Fixed cloud demo dataset: " : "Fixed local demo dataset: "}{DEMO_DATASET_ID}. The official study-area polygon is separate from these generated observations and references.
    </div>
    <label className="mb-4 block text-xs text-slate-400">Filter displayed results
      <input value={filter} onChange={(event) => setFilter(event.target.value)} className="ml-2 rounded border border-white/10 bg-white/5 px-2 py-1 text-white" />
    </label>
    <div className="space-y-4">
      {queries.map((spec) => {
        const result = results[spec.key];
        const records = Array.isArray(result?.records) ? result.records as Record<string, unknown>[] : [];
        const visible = records.filter((record) => !filter || JSON.stringify(record).toLowerCase().includes(filter.toLowerCase()));
        const limitations = Array.isArray(result?.limitations) ? result.limitations as string[] : [];
        const byStreet = result?.by_street && typeof result.by_street === "object" ? result.by_street as Record<string, Record<string, unknown>[]> : null;
        return <section key={spec.key} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="m-0 text-base font-bold text-white">{spec.title}</h2><p className="mb-0 mt-1 text-xs text-slate-400">{spec.explanation}</p><p className="mb-0 mt-2 text-[11px] text-slate-500">Criteria: {spec.criteria}</p></div>
            <button onClick={() => void run(spec)} disabled={loading[spec.key]} className="rounded-lg bg-cyan-500 px-3 py-2 text-xs font-bold text-slate-950 disabled:opacity-50">
              {loading[spec.key] ? "Running…" : "Run Query"}
            </button>
          </div>
          {errors[spec.key] && <div role="alert" className="mt-3 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-xs text-red-200">{errors[spec.key]} <button className="ml-2 underline" onClick={() => void run(spec)}>Retry</button></div>}
          {result && <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-300"><span>Results: {printable(result.result_count)}</span><span>Dataset: {printable(result.dataset_id)}</span><span>Generated: {printable(result.generated_at)}</span><strong className="text-amber-200">{result.simulation ? "SIMULATED DEMONSTRATION DATA" : "Backend data"}</strong></div>
            {spec.key === "routing" && <div className="grid gap-2 text-xs text-slate-300 sm:grid-cols-2">
              <p>Routed workflow metrics: {printable(result.measured_routed_metrics)}</p>
              <p>All-VLM run: {printable(result.all_vlm_status ?? (result.all_vlm_run_performed ? "RUN" : "NOT_RUN"))}</p>
              <p>Quality comparison: {printable(result.quality_comparison_status ?? "NOT_EVALUABLE")}</p>
              <p>All-VLM cost: {printable(result.cost_status ?? (result.hypothetical_all_vlm_estimate as Record<string, unknown> | undefined)?.cost_status ?? "unavailable")}</p>
            </div>}
            {byStreet ? Object.entries(byStreet).map(([street, entries]) => <div key={street}><h3 className="text-sm text-cyan-200">{street} ({entries.length})</h3><ResultTable records={entries.filter((record) => !filter || JSON.stringify(record).toLowerCase().includes(filter.toLowerCase()))} /></div>) : <ResultTable records={visible} />}
            {records.length === 0 && <p className="m-0 rounded bg-white/[0.03] p-3 text-xs text-slate-400">No records matched this query for the selected dataset.</p>}
            {limitations.map((item) => <p key={item} className="m-0 text-[11px] text-amber-100/70">Limitation: {item}</p>)}
            <p className="m-0 text-[10px] text-slate-500">Provenance: {printable(result.provenance)} {result.run_id ? `· Run ${printable(result.run_id)}` : ""}</p>
          </div>}
        </section>;
      })}
    </div>
  </div>;
}

function ResultTable({ records }: { records: Record<string, unknown>[] }) {
  const pageSize = 25;
  const [page, setPage] = useState(1);
  const current = paginate(records, page, pageSize);
  if (!records.length) return null;
  const fields = ["observation_id", "street_id", "asset_type", "building_use", "visible_floor_count", "confidence", "match_status", "discrepancy_type", "expected_asset_condition", "observed_asset_condition", "coverage_status", "coverage_complete", "interval_meters"];
  return <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead><tr>{fields.map((field) => <th key={field} className="border-b border-white/10 px-2 py-2 text-slate-500">{field.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{current.items.map((record, index) => {
    const attributes = record.attributes && typeof record.attributes === "object" ? record.attributes as Record<string, unknown> : {};
    return <tr key={String(record.observation_id ?? record.discrepancy_id ?? record.view_id ?? index)}>{fields.map((field) => <td key={field} className="border-b border-white/5 px-2 py-2 text-slate-300">{printable(record[field] ?? attributes[field])}</td>)}</tr>;
  })}</tbody></table><PaginationControls page={current.page} pageCount={current.pageCount} total={current.total} pageSize={pageSize} onPageChange={setPage} /></div>;
}
