import React from "react";

export default function SensorCard({
  title,
  value,
  unit,
  description,
}) {
  return (
    <div className="sensor-card">
      <div className="sensor-title">
        {title}
      </div>

      <div className="sensor-value">
        {value}
        <span>{unit}</span>
      </div>

      <div className="sensor-description">
        {description}
      </div>

      <div className="sensor-status">
        <span className="status-dot" />
        Sensor Active
      </div>
    </div>
  );
}