jsx
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Droplets,
  FlaskConical,
  Gauge,
  Scale,
  Wifi,
} from "lucide-react";

import {
  getFusion,
  getSession,
  getSessions,
} from "./api";

import MetricCard from "./components/MetricCard";
import SensorCard from "./components/SensorCard";
import PredictionCard from "./components/PredictionCard";
import FlowChart from "./components/FlowChart";
import WeightChart from "./components/WeightChart";
import SessionSelector from "./components/SessionSelector";

import "./App.css";

function App() {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState("");

  const [sessionData, setSessionData] = useState(null);
  const [fusionData, setFusionData] = useState(null);

  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingSession, setLoadingSession] = useState(false);
  const [error, setError] = useState("");

  // ------------------------------------------------------------
  // Load available sessions when the application starts
  // ------------------------------------------------------------
  useEffect(() => {
    async function loadSessions() {
      try {
        setLoadingSessions(true);
        setError("");

        const data = await getSessions();

        setSessions(data);

        // Automatically select the first available session
        if (data.length > 0) {
          setSelectedSession(data[0].id);
        }
      } catch (err) {
        console.error(err);
        setError(
          "Could not connect to the FastAPI backend. Make sure the backend is running on port 8000."
        );
      } finally {
        setLoadingSessions(false);
      }
    }

    loadSessions();
  }, []);

  // ------------------------------------------------------------
  // Load selected session
  // ------------------------------------------------------------
  useEffect(() => {
    if (!selectedSession) return;

    async function loadSelectedSession() {
      try {
        setLoadingSession(true);
        setError("");

        const [session, fusion] = await Promise.all([
          getSession(selectedSession),
          getFusion(selectedSession),
        ]);

        setSessionData(session);
        setFusionData(fusion);
      } catch (err) {
        console.error(err);
        setError(
          "Could not load the selected session. Check the FastAPI backend and dataset."
        );
      } finally {
        setLoadingSession(false);
      }
    }

    loadSelectedSession();
  }, [selectedSession]);

  // ------------------------------------------------------------
  // Extract metadata
  // ------------------------------------------------------------
  const metadata = sessionData?.metadata || sessionData?.meta || {};

  const anomaly =
    metadata?.anomaly ||
    sessionData?.anomaly ||
    "none";

  const targetFlow =
    Number(
      metadata?.target_flow_ml_per_hr ??
        metadata?.target_flow ??
        sessionData?.target_flow_ml_per_hr ??
        0
    ) || 0;

  const bagVolume =
    Number(
      metadata?.bag_volume_ml ??
        metadata?.bag_volume ??
        sessionData?.bag_volume_ml ??
        0
    ) || 0;

  const dropFactor =
    Number(
      metadata?.drop_factor_nominal_gtts_per_ml ??
        metadata?.drop_factor ??
        sessionData?.drop_factor ??
        0
    ) || 0;

  // ------------------------------------------------------------
  // Fusion rows
  // ------------------------------------------------------------
  const fusionRows = useMemo(() => {
    if (!fusionData) return [];

    if (Array.isArray(fusionData)) {
      return fusionData;
    }

    if (Array.isArray(fusionData.rows)) {
      return fusionData.rows;
    }

    if (Array.isArray(fusionData.data)) {
      return fusionData.data;
    }

    return [];
  }, [fusionData]);

  // ------------------------------------------------------------
  // Get latest EKF result
  // ------------------------------------------------------------
  const latestFusion = useMemo(() => {
    if (!fusionRows.length) return null;

    return fusionRows[fusionRows.length - 1];
  }, [fusionRows]);

  // ------------------------------------------------------------
  // Extract current values
  // ------------------------------------------------------------
  const currentFlow =
    Number(
      latestFusion?.fused_flow_ml_per_hr ??
        latestFusion?.fused_flow ??
        latestFusion?.flow_rate ??
        0
    ) || 0;

  const flowStd =
    Number(
      latestFusion?.fused_flow_std ??
        latestFusion?.flow_std ??
        latestFusion?.uncertainty ??
        0
    ) || 0;

  const adaptiveDropFactor =
    Number(
      latestFusion?.fused_drop_factor ??
        latestFusion?.drop_factor ??
        dropFactor
    ) || 0;

  const remainingVolume =
    Number(
      latestFusion?.remaining_vol_ml ??
        latestFusion?.remaining_volume_ml ??
        latestFusion?.remaining_volume ??
        0
    ) || 0;

  const remainingTime =
    Number(
      latestFusion?.remaining_time_min ??
        latestFusion?.remaining_time_minutes ??
        0
    ) || 0;

  const remainingLow =
    Number(
      latestFusion?.remaining_time_low_min ??
        latestFusion?.remaining_low_min ??
        0
    ) || 0;

  const remainingHigh =
    Number(
      latestFusion?.remaining_time_high_min ??
        latestFusion?.remaining_high_min ??
        0
    ) || 0;

  const loadCellFlow =
    Number(
      latestFusion?.weight_only_flow ??
        latestFusion?.load_cell_flow ??
        0
    ) || 0;

  const irFlow =
    Number(
      latestFusion?.drop_only_flow ??
        latestFusion?.ir_flow ??
        0
    ) || 0;

  // ------------------------------------------------------------
  // Sensor agreement
  // ------------------------------------------------------------
  const sensorDifference = Math.abs(loadCellFlow - irFlow);

  const sensorAgreement =
    currentFlow > 0
      ? Math.max(
          0,
          100 - (sensorDifference / Math.max(currentFlow, 1)) * 100
        )
      : 0;

  const agreementLabel =
    sensorAgreement >= 90
      ? "Excellent"
      : sensorAgreement >= 75
      ? "Good"
      : sensorAgreement >= 50
      ? "Warning"
      : "Poor";

  // ------------------------------------------------------------
  // Confidence
  //
  // This is a prototype confidence score derived from EKF
  // uncertainty and sensor agreement.
  // It is NOT a clinical confidence metric.
  // ------------------------------------------------------------
  const confidence = useMemo(() => {
    if (!currentFlow) return 0;

    const uncertaintyPenalty =
      (flowStd / Math.max(currentFlow, 1)) * 100;

    const score =
      0.65 * sensorAgreement +
      0.35 * Math.max(0, 100 - uncertaintyPenalty * 2);

    return Math.max(0, Math.min(100, score));
  }, [currentFlow, flowStd, sensorAgreement]);

  // ------------------------------------------------------------
  // Status
  // ------------------------------------------------------------
  const isAnomaly =
    anomaly &&
    anomaly.toLowerCase() !== "none" &&
    anomaly.toLowerCase() !== "normal";

  const deviceStatus = loadingSession
    ? "Loading"
    : "Online";

  // ------------------------------------------------------------
  // Format remaining time
  // ------------------------------------------------------------
  function formatTime(minutes) {
    if (!Number.isFinite(minutes) || minutes <= 0) {
      return "--";
    }

    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);

    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }

    return `${mins} min`;
  }

  // ------------------------------------------------------------
  // Convert raw fusion data to chart data
  // ------------------------------------------------------------
  const flowChartData = useMemo(() => {
    return fusionRows.map((row, index) => ({
      time:
        Number(row.t_mid_s ?? row.time_s ?? row.time ?? index) || index,

      fused:
        Number(
          row.fused_flow_ml_per_hr ??
            row.fused_flow ??
            row.flow_rate ??
            0
        ) || 0,

      loadCell:
        Number(
          row.weight_only_flow ??
            row.load_cell_flow ??
            0
        ) || 0,

      ir:
        Number(
          row.drop_only_flow ??
            row.ir_flow ??
            0
        ) || 0,

      trueFlow:
        Number(
          row.true_flow ??
            0
        ) || 0,
    }));
  }, [fusionRows]);

  // ------------------------------------------------------------
  // Weight chart
  //
  // The backend may expose raw weight rows separately.
  // ------------------------------------------------------------
  const weightChartData = useMemo(() => {
    const rows =
      sessionData?.weight_sensor ||
      sessionData?.weight ||
      sessionData?.weight_rows ||
      [];

    if (!Array.isArray(rows)) return [];

    return rows.map((row, index) => ({
      time:
        Number(
          row.time_s ??
            row.timestamp_s ??
            row.time ??
            index
        ) || index,

      weight:
        Number(
          row.weight_g ??
            row.weight ??
            row.mass_g ??
            0
        ) || 0,
    }));
  }, [sessionData]);

  // ------------------------------------------------------------
  // Empty / loading screen
  // ------------------------------------------------------------
  if (loadingSessions) {
    return (
      <div className="app">
        <div className="loading-screen">
          <Activity size={36} />
          <h2>Loading IV Monitoring System...</h2>
          <p>Connecting to the local FastAPI backend.</p>
        </div>
      </div>
    );
  }

  // ------------------------------------------------------------
  // Main UI
  // ------------------------------------------------------------
  return (
    <div className="app">

      {/* ========================================================
          HEADER
      ======================================================== */}
      <header className="app-header">

        <div className="brand">
          <div className="brand-icon">
            <Droplets size={28} />
          </div>

          <div>
            <h1>Dual-Sensor IV Monitor</h1>
            <p>
              Predictive infusion monitoring using sensor fusion
            </p>
          </div>
        </div>

        <div className="header-right">

          <div className="simulation-badge">
            <FlaskConical size={16} />
            <span>SIMULATION / VALIDATION DATA</span>
          </div>

          <div className="connection-status">
            <span className="status-dot" />
            <Wifi size={16} />
            <span>{deviceStatus}</span>
          </div>

        </div>

      </header>


      {/* ========================================================
          ERROR
      ======================================================== */}
      {error && (
        <div className="error-banner">
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      )}


      {/* ========================================================
          SESSION CONTROLS
      ======================================================== */}
      <section className="control-section">

        <div className="control-card">

          <div>
            <h3>Validation Session</h3>
            <p>
              Select a synthetic experiment from the research dataset.
            </p>
          </div>

          <SessionSelector
            sessions={sessions}
            selectedSession={selectedSession}
            onChange={setSelectedSession}
          />

        </div>

      </section>


      {/* ========================================================
          SESSION INFORMATION
      ======================================================== */}
      {selectedSession && (
        <section className="session-info">

          <div className="session-title">
            <div>
              <span className="eyebrow">
                CURRENT SESSION
              </span>

              <h2>{selectedSession}</h2>
            </div>

            <div
              className={`anomaly-badge ${
                isAnomaly ? "danger" : "normal"
              }`}
            >
              {isAnomaly ? (
                <>
                  <AlertTriangle size={16} />
                  {anomaly}
                </>
              ) : (
                <>
                  <CheckCircle2 size={16} />
                  Normal
                </>
              )}
            </div>
          </div>

        </section>
      )}


      {/* ========================================================
          PRIMARY METRICS
      ======================================================== */}
      <section className="metrics-grid">

        <MetricCard
          title="Fused Flow Rate"
          value={currentFlow.toFixed(1)}
          unit="mL/hr"
          icon={<Gauge size={22} />}
          subtitle={
            targetFlow > 0
              ? `Target: ${targetFlow.toFixed(1)} mL/hr`
              : "EKF estimate"
          }
        />

        <MetricCard
          title="Remaining Volume"
          value={
            remainingVolume > 0
              ? remainingVolume.toFixed(1)
              : "--"
          }
          unit="mL"
          icon={<Droplets size={22} />}
          subtitle={
            bagVolume > 0
              ? `Initial bag: ${bagVolume.toFixed(0)} mL`
              : "Estimated"
          }
        />

        <MetricCard
          title="Time Remaining"
          value={formatTime(remainingTime)}
          unit=""
          icon={<Clock3 size={22} />}
          subtitle={
            remainingLow > 0 && remainingHigh > 0
              ? `Range: ${formatTime(
                  remainingLow
                )} – ${formatTime(remainingHigh)}`
              : "Prediction"
          }
        />

        <MetricCard
          title="Fusion Confidence"
          value={confidence.toFixed(0)}
          unit="%"
          icon={<Activity size={22} />}
          subtitle="Prototype confidence estimate"
        />

      </section>


      {/* ========================================================
          SENSOR CARDS
      ======================================================== */}
      <section className="sensor-section">

        <div className="section-heading">
          <div>
            <span className="eyebrow">
              SENSOR FUSION
            </span>

            <h2>Independent Flow Measurements</h2>
          </div>

          <div className="agreement-indicator">
            <span>Agreement</span>

            <strong>
              {sensorAgreement.toFixed(0)}%
            </strong>

            <small>{agreementLabel}</small>
          </div>
        </div>


        <div className="sensor-grid">

          <SensorCard
            title="Load Cell"
            value={loadCellFlow.toFixed(1)}
            unit="mL/hr"
            icon={<Scale size={22} />}
            description="Mass-loss based flow estimate"
          />

          <SensorCard
            title="IR Drop Sensor"
            value={irFlow.toFixed(1)}
            unit="mL/hr"
            icon={<Activity size={22} />}
            description={
              adaptiveDropFactor > 0
                ? `Adaptive factor: ${adaptiveDropFactor.toFixed(
                    2
                  )} gtts/mL`
                : "Drop-count based flow estimate"
            }
          />

          <SensorCard
            title="EKF Fusion"
            value={currentFlow.toFixed(1)}
            unit="mL/hr"
            icon={<Gauge size={22} />}
            description={
              flowStd > 0
                ? `Uncertainty: ±${flowStd.toFixed(
                    2
                  )} mL/hr`
                : "Fused state estimate"
            }
            highlighted
          />

        </div>

      </section>


      {/* ========================================================
          CHARTS
      ======================================================== */}
      <section className="charts-section">

        <div className="chart-card">

          <div className="chart-header">
            <div>
              <span className="eyebrow">
                FLOW ANALYSIS
              </span>

              <h3>Sensor Fusion Over Time</h3>
            </div>

            <div className="chart-legend">

              <span>
                <i className="legend fused" />
                EKF Fusion
              </span>

              <span>
                <i className="legend load" />
                Load Cell
              </span>

              <span>
                <i className="legend ir" />
                IR Sensor
              </span>

            </div>
          </div>

          <div className="chart-container">

            {flowChartData.length > 0 ? (
              <FlowChart data={flowChartData} />
            ) : (
              <div className="empty-chart">
                <Activity size={28} />
                <p>No fusion data available.</p>
              </div>
            )}

          </div>

        </div>


        <div className="chart-card">

          <div className="chart-header">

            <div>
              <span className="eyebrow">
                BAG MONITORING
              </span>

              <h3>Bag Weight Over Time</h3>
            </div>

            <div className="chart-stat">
              <Scale size={18} />
              <span>
                {bagVolume > 0
                  ? `${bagVolume.toFixed(0)} mL initial`
                  : "Weight data"}
              </span>
            </div>

          </div>

          <div className="chart-container">

            {weightChartData.length > 0 ? (
              <WeightChart data={weightChartData} />
            ) : (
              <div className="empty-chart">
                <Scale size={28} />
                <p>
                  Weight chart data will appear when the
                  backend exposes the sensor rows.
                </p>
              </div>
            )}

          </div>

        </div>

      </section>


      {/* ========================================================
          PREDICTION
      ======================================================== */}
      <section className="prediction-section">

        <div className="section-heading">

          <div>
            <span className="eyebrow">
              PREDICTIVE MONITORING
            </span>

            <h2>Infusion Completion Prediction</h2>
          </div>

        </div>


        <PredictionCard
          remainingTime={remainingTime}
          remainingLow={remainingLow}
          remainingHigh={remainingHigh}
          remainingVolume={remainingVolume}
          confidence={confidence}
          currentFlow={currentFlow}
        />

      </section>


      {/* ========================================================
          ADAPTIVE CALIBRATION
      ======================================================== */}
      <section className="calibration-section">

        <div className="calibration-card">

          <div className="calibration-icon">
            <Activity size={22} />
          </div>

          <div className="calibration-content">

            <span className="eyebrow">
              ADAPTIVE CALIBRATION
            </span>

            <h3>
              Effective Drop Factor
            </h3>

            <p>
              The EKF estimates the effective drop factor from
              the relationship between measured mass-loss flow
              and observed drop rate.
            </p>

          </div>

          <div className="calibration-value">

            <strong>
              {adaptiveDropFactor > 0
                ? adaptiveDropFactor.toFixed(2)
                : "--"}
            </strong>

            <span>gtts/mL</span>

            {dropFactor > 0 && (
              <small>
                Nominal: {dropFactor.toFixed(2)}
              </small>
            )}

          </div>

        </div>

      </section>


      {/* ========================================================
          UNCERTAINTY
      ======================================================== */}
      <section className="uncertainty-section">

        <div className="uncertainty-card">

          <div className="uncertainty-left">

            <div className="uncertainty-icon">
              <Activity size={22} />
            </div>

            <div>
              <span className="eyebrow">
                ESTIMATION UNCERTAINTY
              </span>

              <h3>
                EKF Flow Uncertainty
              </h3>

              <p>
                Lower uncertainty generally indicates greater
                consistency between the sensor measurements and
                the current model state.
              </p>
            </div>

          </div>

          <div className="uncertainty-value">

            <strong>
              {flowStd > 0
                ? `±${flowStd.toFixed(2)}`
                : "--"}
            </strong>

            <span>mL/hr</span>

          </div>

        </div>

      </section>


      {/* ========================================================
          VALIDATION INFORMATION
      ======================================================== */}
      <section className="validation-section">

        <div className="validation-card">

          <div className="validation-header">

            <FlaskConical size={22} />

            <div>
              <h3>
                Research / Validation Mode
              </h3>

              <p>
                This dashboard is connected to the synthetic
                validation dataset included in the project
                repository.
              </p>
            </div>

          </div>


          <div className="validation-grid">

            <div>
              <span>Session</span>
              <strong>
                {selectedSession || "--"}
              </strong>
            </div>

            <div>
              <span>Target Flow</span>
              <strong>
                {targetFlow > 0
                  ? `${targetFlow.toFixed(1)} mL/hr`
                  : "--"}
              </strong>
            </div>

            <div>
              <span>Nominal Drop Factor</span>
              <strong>
                {dropFactor > 0
                  ? `${dropFactor.toFixed(2)} gtts/mL`
                  : "--"}
              </strong>
            </div>

            <div>
              <span>Samples / Windows</span>
              <strong>
                {fusionRows.length || "--"}
              </strong>
            </div>

          </div>

        </div>

      </section>


      {/* ========================================================
          DISCLAIMER
      ======================================================== */}
      <footer className="app-footer">

        <div className="footer-warning">

          <AlertTriangle size={18} />

          <p>
            <strong>Prototype / Research Use Only.</strong>{" "}
            This system is a university engineering prototype
            for sensor-fusion and predictive-monitoring research.
            It is not a medical device and must not be used to
            make clinical decisions or control infusion delivery.
          </p>

        </div>

        <p className="footer-copy">
          Dual-Sensor Predictive IV Monitoring System
        </p>

      </footer>

    </div>
  );
}

export default App;
