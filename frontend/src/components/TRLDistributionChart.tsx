import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrlCount } from "../types";

interface TRLDistributionChartProps {
  distribution: TrlCount[];
  height?: number;
  /** Level to highlight (the predicted TRL). */
  highlight?: number | null;
  /** Optional label for the y-axis unit. */
  unitLabel?: string;
}

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #E5EAF2",
  boxShadow: "0 18px 40px -24px rgba(10,22,40,0.45)",
  fontSize: 12,
  padding: "8px 10px",
} as const;

/** Real TRL 1-9 distribution chart. Empty counts are shown as zero, not hidden. */
export default function TRLDistributionChart({
  distribution,
  height = 220,
  highlight = null,
  unitLabel = "assessment(s)",
}: TRLDistributionChartProps) {
  const data = Array.from({ length: 9 }, (_, i) => {
    const level = i + 1;
    const found = distribution.find((d) => d.trl === level);
    return { name: `TRL ${level}`, trl: level, count: found?.count ?? 0 };
  });

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="4 6" stroke="#EDF1F7" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: "#8a97a8" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "#8a97a8" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(13,148,136,0.06)" }}
            contentStyle={tooltipStyle}
            formatter={(value) => [`${value} ${unitLabel}`, "Count"]}
          />
          <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={40}>
            {data.map((entry) => (
              <Cell
                key={entry.trl}
                fill={
                  highlight === entry.trl
                    ? "#0f766e"
                    : entry.count > 0
                      ? "#2dd4bf"
                      : "#e2e8f0"
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
