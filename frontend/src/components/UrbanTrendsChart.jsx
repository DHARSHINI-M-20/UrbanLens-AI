import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";

const data = [
  { month: "Jan", properties: 120 },
  { month: "Feb", properties: 145 },
  { month: "Mar", properties: 160 },
  { month: "Apr", properties: 185 },
  { month: "May", properties: 210 },
  { month: "Jun", properties: 235 }
];

function UrbanTrendsChart() {
  return (
    <div className="chart-card">
      <h2>Urban Development Trends</h2>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />

          <Line
            type="monotone"
            dataKey="properties"
            stroke="#2563eb"
            strokeWidth={3}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default UrbanTrendsChart;