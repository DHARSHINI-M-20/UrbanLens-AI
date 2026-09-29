import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  assetData,
  buildingUseData,
  confidenceData,
  floorDistributionData as floorData,
  matchingData,
  aiRoutingData as routingData,
} from "../data/mockData";

const COLORS = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f87171"];

const tooltipStyle = {
  background: "#0f172a",
  border: "1px solid rgba(148,163,184,0.2)",
  borderRadius: 12,
  color: "#e2e8f0",
  fontSize: 12,
};

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
      <div className="mb-4">
        <h3 className="m-0 font-bold text-white">{title}</h3>
        <p className="m-0 mt-1 text-xs text-slate-500">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

export default function Analytics() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartCard title="Building Use" subtitle="Residential · Commercial · Mixed-use · Institutional">
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie data={buildingUseData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85} innerRadius={48}>
              {buildingUseData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Floor Distribution" subtitle="1 / 2 / 3 / 4+ floors detected across buildings">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={floorData}>
            <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
            <Bar dataKey="value" fill="#38bdf8" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Asset Distribution" subtitle="Streetlights, electric poles and other street infrastructure">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={assetData}>
            <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
            <Bar dataKey="value" fill="#22d3ee" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Matching Status" subtitle="Matched · Partial · Unmatched · Not verified">
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie data={matchingData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85}>
              {matchingData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="AI Confidence" subtitle="High / Medium / Low confidence distribution">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={confidenceData}>
            <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={{ stroke: "#1e293b" }} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
            <Bar dataKey="value" fill="#818cf8" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="AI Routing" subtitle="Lightweight model-first routing vs. VLM escalation">
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie data={routingData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={85}>
              <Cell fill="#22d3ee" />
              <Cell fill="#818cf8" />
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
