import React from "react";

export default function MetricCard({
  title,
  value,
  subtitle,
  icon,
}) {
  return (
    <div className="metric-card">
      <div className="metric-header">
        <span>{title}</span>
        <span className="metric-icon">{icon}</span>
      </div>

      <div className="metric-value">
        {value}
      </div>

      <div className="metric-subtitle">
        {subtitle}
      </div>
    </div>
  );
}