import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function WeightChart({ data }) {
  return (
    <div className="chart-card">

      <div className="chart-title">
        IV Bag Weight
      </div>

      <div className="chart-subtitle">
        Real-time simulated load-cell measurement
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>

          <CartesianGrid strokeDasharray="3 3" />

          <XAxis dataKey="time" />

          <YAxis />

          <Tooltip />

          <Line
            type="monotone"
            dataKey="weight"
            name="Weight"
            stroke="#7c3aed"
            strokeWidth={3}
            dot={false}
          />

        </LineChart>
      </ResponsiveContainer>

    </div>
  );
}