import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export default function FlowChart({ data }) {
  return (
    <div className="chart-card">

      <div className="chart-title">
        Live Flow Rate
      </div>

      <div className="chart-subtitle">
        Comparison of both sensors and EKF fused estimate
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>

          <CartesianGrid strokeDasharray="3 3" />

          <XAxis dataKey="time" />

          <YAxis
            label={{
              value: "mL/hr",
              angle: -90,
              position: "insideLeft",
            }}
          />

          <Tooltip />

          <Legend />

          <Line
            type="monotone"
            dataKey="loadCell"
            name="Load Cell"
            stroke="#2563eb"
            dot={false}
          />

          <Line
            type="monotone"
            dataKey="ir"
            name="IR Sensor"
            stroke="#f59e0b"
            dot={false}
          />

          <Line
            type="monotone"
            dataKey="fused"
            name="EKF Fusion"
            stroke="#16a34a"
            strokeWidth={3}
            dot={false}
          />

        </LineChart>
      </ResponsiveContainer>

    </div>
  );
}