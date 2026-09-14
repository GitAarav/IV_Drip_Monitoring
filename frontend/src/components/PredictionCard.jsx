import React from "react";

export default function PredictionCard({
  remainingTime,
  confidence,
}) {
  const hours = Math.floor(remainingTime / 60);
  const minutes = remainingTime % 60;

  return (
    <div className="prediction-card">

      <div className="prediction-label">
        ESTIMATED TIME REMAINING
      </div>

      <div className="prediction-time">
        {hours}h {minutes}m
      </div>

      <div className="prediction-completion">
        Estimated completion in approximately{" "}
        {remainingTime} minutes
      </div>

      <div className="confidence-section">

        <div className="confidence-header">
          <span>Prediction Confidence</span>
          <strong>{confidence}%</strong>
        </div>

        <div className="confidence-bar">
          <div
            className="confidence-fill"
            style={{ width: `${confidence}%` }}
          />
        </div>

        <div className="confidence-text">
          Prediction range is based on current sensor
          uncertainty and fused flow estimation.
        </div>

      </div>
    </div>
  );
}