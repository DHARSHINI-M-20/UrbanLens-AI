import type { ReactNode } from "react";
import {
  Bar, BarChart, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { useDashboard } from "../context/DashboardContext";

const COLORS = ["#38bdf8", "#34d399", "#fbbf24", "#f87171", "#c084fc", "#fb7185"];
const tooltipStyle = {
  background: "#0f172a", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 8,
  color: "#e2e8f0", fontSize: 12,
};

type ChartRow = { name: string; value: number };

function rows(value: unknown): ChartRow[] {
  if (!value || typeof value !== "object") return [];
  return Object.entries(value as Record<string, unknown>).map(([rawName, count]) => ({
    name: ({ small_model: "Small model", vlm_escalation: "Nova Lite (real)", simulated_escalation: "Simulated Nova mock" } as Record<string, string>)[rawName] ?? rawName,
    value: Number(count ?? 0),
  }));
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
      <h3 className="m-0 mb-4 text-sm font-bold text-white">{title}</h3>
      {children}
    </section>
  );
}

function BarPanel({ title, data, color = "#38bdf8" }: { title: string; data: ChartRow[]; color?: string }) {
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
          <Bar dataKey="value" fill={color} radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function PiePanel({ title, data }: { title: string; data: ChartRow[] }) {
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={86} innerRadius={42}>
            {data.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 10, color: "#94a3b8" }} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export default function Analytics() {
  const { summary, observations } = useDashboard();
  const lowConfidence = observations.filter((item) => Number(item.confidence ?? 0) < 0.7).length;
  const otherConfidence = observations.length - lowConfidence;

  return (
    <div>
      <p className="mb-4 text-[11px] text-slate-500">All distributions are calculated from persisted API records in the active dataset.</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <PiePanel title="Building Use" data={rows(summary?.building_use_distribution)} />
        <BarPanel title="Visible Floor Distribution" data={rows(summary?.floor_distribution)} color="#34d399" />
        <BarPanel title="Asset Type Distribution" data={rows(summary?.asset_type_distribution)} color="#fbbf24" />
        <PiePanel title="Match Status" data={rows(summary?.match_status_distribution)} />
        <BarPanel title="Discrepancies by Street" data={rows(summary?.discrepancies_by_street)} color="#fb7185" />
        <PiePanel title="Confidence Review Threshold" data={[
          { name: "Low confidence", value: lowConfidence }, { name: "Other observations", value: otherConfidence },
        ]} />
        <PiePanel title="Processing Route" data={rows(summary?.processing_route_distribution)} />
      </div>
    </div>
  );
}
