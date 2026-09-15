import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000/api";

function App() {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState("");
  const [sessionData, setSessionData] = useState(null);
  const [fusionData, setFusionData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingSession, setLoadingSession] = useState(false);
  const [error, setError] = useState("");

  // --------------------------------------------------
  // Load available sessions
  // --------------------------------------------------
  useEffect(() => {
    async function loadSessions() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(`${API_URL}/sessions`);

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const data = await response.json();

        console.log("Sessions from backend:", data);

        const sessionList = Array.isArray(data)
          ? data
          : data.sessions || [];

        setSessions(sessionList);

        if (sessionList.length > 0) {
          const first =
            typeof sessionList[0] === "string"
              ? sessionList[0]
              : sessionList[0].id;

          setSelectedSession(first);
        }
      } catch (err) {
        console.error("Session loading error:", err);

        setError(
          "Cannot connect to FastAPI. Start the backend with: uvicorn main:app --reload"
        );
      } finally {
        setLoading(false);
      }
    }

    loadSessions();
  }, []);

  // --------------------------------------------------
  // Load selected session
  // --------------------------------------------------
  useEffect(() => {
    if (!selectedSession) return;

    async function loadSession() {
      try {
        setLoadingSession(true);
        setError("");

        const [sessionResponse, fusionResponse] =
          await Promise.all([
            fetch(
              `${API_URL}/sessions/${selectedSession}`
            ),
            fetch(
              `${API_URL}/sessions/${selectedSession}/fusion`
            ),
          ]);

        if (!sessionResponse.ok) {
          throw new Error(
            `Session API returned ${sessionResponse.status}`
          );
        }

        if (!fusionResponse.ok) {
          throw new Error(
            `Fusion API returned ${fusionResponse.status}`
          );
        }

        const session = await sessionResponse.json();
        const fusion = await fusionResponse.json();

        console.log("Selected session:", session);
        console.log("Fusion:", fusion);

        setSessionData(session);

        const rows = Array.isArray(fusion)
          ? fusion
          : fusion.rows || fusion.data || [];

        setFusionData(rows);
      } catch (err) {
        console.error("Session loading error:", err);
        setError(
          `Could not load session "${selectedSession}". Check the backend console.`
        );
      } finally {
        setLoadingSession(false);
      }
    }

    loadSession();
  }, [selectedSession]);

  // --------------------------------------------------
  // Latest EKF result
  // --------------------------------------------------
  const latest = useMemo(() => {
    if (!fusionData.length) return null;

    return fusionData[fusionData.length - 1];
  }, [fusionData]);

  // --------------------------------------------------
  // Values from EKF
  // --------------------------------------------------
  const fusedFlow = Number(
    latest?.fused_flow_ml_per_hr ?? 0
  );

  const flowStd = Number(
    latest?.fused_flow_std ?? 0
  );

  const dropFactor = Number(
    latest?.fused_drop_factor ?? 0
  );

  const loadCellFlow = Number(
    latest?.weight_only_flow ?? 0
  );

  const irFlow = Number(
    latest?.drop_only_flow ?? 0
  );

  const remainingVolume = Number(
    latest?.remaining_vol_ml ?? 0
  );

  const remainingTime = Number(
    latest?.remaining_time_min ?? 0
  );

  const remainingLow = Number(
    latest?.remaining_time_low_min ?? 0
  );

  const remainingHigh = Number(
    latest?.remaining_time_high_min ?? 0
  );

  // --------------------------------------------------
  // Metadata
  // --------------------------------------------------
  const metadata =
    sessionData?.metadata ||
    sessionData?.meta ||
    {};

  const targetFlow = Number(
    metadata?.target_flow_ml_per_hr ??
      sessionData?.target_flow_ml_per_hr ??
      0
  );

  const bagVolume = Number(
    metadata?.bag_volume_ml ??
      sessionData?.bag_volume_ml ??
      0
  );

  const nominalDropFactor = Number(
    metadata?.drop_factor_nominal_gtts_per_ml ??
      0
  );

  const anomaly =
    metadata?.anomaly ||
    sessionData?.anomaly ||
    "none";

  const isAnomaly =
    anomaly &&
    anomaly.toLowerCase() !== "none" &&
    anomaly.toLowerCase() !== "normal";

  // --------------------------------------------------
  // Sensor agreement
  // --------------------------------------------------
  const difference = Math.abs(
    loadCellFlow - irFlow
  );

  const agreement =
    fusedFlow > 0
      ? Math.max(
          0,
          Math.min(
            100,
            100 -
              (difference /
                Math.max(fusedFlow, 1)) *
                100
          )
        )
      : 0;

  // --------------------------------------------------
  // Prototype confidence
  // --------------------------------------------------
  const confidence =
    fusedFlow > 0
      ? Math.max(
          0,
          Math.min(
            100,
            agreement * 0.7 +
              Math.max(
                0,
                100 -
                  (flowStd /
                    Math.max(fusedFlow, 1)) *
                    100
              ) *
                0.3
          )
        )
      : 0;

  // --------------------------------------------------
  // Format time
  // --------------------------------------------------
  function formatTime(minutes) {
    if (!Number.isFinite(minutes)) {
      return "--";
    }

    if (minutes <= 0) {
      return "--";
    }

    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);

    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }

    return `${mins} min`;
  }

  // --------------------------------------------------
  // Small metric component
  // --------------------------------------------------
  function Metric({
    title,
    value,
    unit,
    description,
  }) {
    return (
      <div className="metric-card">
        <div className="metric-title">
          {title}
        </div>

        <div className="metric-value">
          {value}
          {unit && (
            <span className="metric-unit">
              {unit}
            </span>
          )}
        </div>

        <div className="metric-description">
          {description}
        </div>
      </div>
    );
  }

  // --------------------------------------------------
  // Sensor component
  // --------------------------------------------------
  function Sensor({
    title,
    value,
    description,
    active,
  }) {
    return (
      <div
        className={`sensor-card ${
          active ? "sensor-active" : ""
        }`}
      >
        <div className="sensor-header">
          <span className="sensor-dot" />
          <strong>{title}</strong>
        </div>

        <div className="sensor-value">
          {Number.isFinite(value)
            ? value.toFixed(1)
            : "--"}

          <span> mL/hr</span>
        </div>

        <div className="sensor-description">
          {description}
        </div>
      </div>
    );
  }

  // --------------------------------------------------
  // Loading state
  // --------------------------------------------------
  if (loading) {
    return (
      <div className="app">
        <div className="loading">
          <div className="loading-spinner" />
          <h2>Dual-Sensor IV Monitor</h2>
          <p>
            Connecting to the monitoring backend...
          </p>
        </div>
      </div>
    );
  }

  // --------------------------------------------------
  // Main page
  // --------------------------------------------------
  return (
    <div className="app">

      {/* HEADER */}
      <header className="header">

        <div>
          <div className="brand">
            <span className="brand-icon">
              💧
            </span>

            <div>
              <h1>
                Dual-Sensor IV Monitor
              </h1>

              <p>
                Predictive infusion monitoring
                using EKF sensor fusion
              </p>
            </div>
          </div>
        </div>

        <div className="header-status">

          <div className="simulation">
            🧪 SIMULATION / VALIDATION
          </div>

          <div className="online">
            <span />
            Backend Connected
          </div>

        </div>

      </header>


      {/* ERROR */}
      {error && (
        <div className="error-box">
          ⚠️
          <div>
            <strong>
              Backend connection problem
            </strong>

            <p>{error}</p>
          </div>
        </div>
      )}


      {/* SESSION SELECTOR */}
      <section className="section">

        <div className="section-header">

          <div>
            <div className="eyebrow">
              VALIDATION SESSION
            </div>

            <h2>
              Select Experiment
            </h2>
          </div>

          <select
            value={selectedSession}
            onChange={(event) =>
              setSelectedSession(
                event.target.value
              )
            }
          >
            <option value="">
              Select a session
            </option>

            {sessions.map((session, index) => {

              const id =
                typeof session === "string"
                  ? session
                  : session.id;

              return (
                <option
                  key={id || index}
                  value={id}
                >
                  {id}
                </option>
              );
            })}
          </select>

        </div>

      </section>


      {/* CURRENT SESSION */}
      {selectedSession && (
        <section className="current-session">

          <div>
            <div className="eyebrow">
              CURRENT SESSION
            </div>

            <h2>
              {selectedSession}
            </h2>
          </div>

          <div
            className={
              isAnomaly
                ? "anomaly danger"
                : "anomaly normal"
            }
          >
            {isAnomaly
              ? `⚠ ${anomaly}`
              : "✓ NORMAL"}
          </div>

        </section>
      )}


      {/* MAIN METRICS */}
      <section className="metrics">

        <Metric
          title="Fused Flow Rate"
          value={
            fusedFlow
              ? fusedFlow.toFixed(1)
              : "--"
          }
          unit="mL/hr"
          description={
            targetFlow
              ? `Target ${targetFlow.toFixed(
                  1
                )} mL/hr`
              : "EKF estimate"
          }
        />

        <Metric
          title="Remaining Volume"
          value={
            remainingVolume
              ? remainingVolume.toFixed(1)
              : "--"
          }
          unit="mL"
          description={
            bagVolume
              ? `Initial bag ${bagVolume.toFixed(
                  0
                )} mL`
              : "Estimated"
          }
        />

        <Metric
          title="Time Remaining"
          value={formatTime(
            remainingTime
          )}
          description={
            remainingLow > 0 &&
            remainingHigh > 0
              ? `${formatTime(
                  remainingLow
                )} – ${formatTime(
                  remainingHigh
                )}`
              : "EKF prediction"
          }
        />

        <Metric
          title="Confidence"
          value={
            confidence
              ? confidence.toFixed(0)
              : "--"
          }
          unit="%"
          description="Prototype confidence"
        />

      </section>


      {/* SENSOR FUSION */}
      <section className="section">

        <div className="section-header">

          <div>
            <div className="eyebrow">
              SENSOR FUSION
            </div>

            <h2>
              Independent Measurements
            </h2>
          </div>

          <div className="agreement">
            <span>
              Sensor Agreement
            </span>

            <strong>
              {agreement.toFixed(0)}%
            </strong>
          </div>

        </div>


        <div className="sensors">

          <Sensor
            title="Load Cell"
            value={loadCellFlow}
            description="Mass-loss based flow estimate"
          />

          <Sensor
            title="IR Drop Sensor"
            value={irFlow}
            description="Drop-count based flow estimate"
          />

          <Sensor
            title="EKF Fusion"
            value={fusedFlow}
            description={`Uncertainty ±${flowStd.toFixed(
              2
            )} mL/hr`}
            active
          />

        </div>

      </section>


      {/* FLOW GRAPH */}
      <section className="section">

        <div className="section-header">

          <div>
            <div className="eyebrow">
              FLOW ANALYSIS
            </div>

            <h2>
              EKF Flow Estimate
            </h2>
          </div>

          <div className="data-count">
            {fusionData.length} windows
          </div>

        </div>


        <div className="chart">

          {fusionData.length === 0 ? (
            <div className="no-data">
              <div>
                📊
              </div>

              <p>
                No fusion data available yet.
              </p>
            </div>
          ) : (
            <div className="bars">

              {fusionData
                .slice(-40)
                .map((row, index) => {

                  const value = Number(
                    row.fused_flow_ml_per_hr ??
                      0
                  );

                  const max =
                    Math.max(
                      ...fusionData.map(
                        (r) =>
                          Number(
                            r.fused_flow_ml_per_hr ??
                              0
                          )
                      ),
                      1
                    );

                  const height =
                    Math.max(
                      5,
                      (value / max) * 100
                    );

                  return (
                    <div
                      className="bar-wrapper"
                      key={index}
                    >
                      <div
                        className="bar"
                        style={{
                          height: `${height}%`,
                        }}
                        title={`${value.toFixed(
                          1
                        )} mL/hr`}
                      />
                    </div>
                  );
                })}

            </div>
          )}

        </div>

      </section>


      {/* CALIBRATION + PREDICTION */}
      <section className="two-column">

        <div className="info-card">

          <div className="eyebrow">
            ADAPTIVE CALIBRATION
          </div>

          <h2>
            Effective Drop Factor
          </h2>

          <div className="large-number">
            {dropFactor
              ? dropFactor.toFixed(2)
              : "--"}

            <span>
              gtts/mL
            </span>
          </div>

          <p>
            The EKF continuously estimates the
            effective drop factor from the
            relationship between flow and observed
            drop rate.
          </p>

          {nominalDropFactor > 0 && (
            <div className="small-info">
              Nominal:
              {" "}
              {nominalDropFactor.toFixed(
                2
              )}
              {" "}
              gtts/mL
            </div>
          )}

        </div>


        <div className="info-card">

          <div className="eyebrow">
            PREDICTION
          </div>

          <h2>
            Infusion Completion
          </h2>

          <div className="large-number">
            {formatTime(
              remainingTime
            )}
          </div>

          <p>
            Estimated time until the simulated
            infusion volume is depleted.
          </p>

          {remainingLow > 0 &&
            remainingHigh > 0 && (
              <div className="small-info">
                Prediction range:
                {" "}
                {formatTime(
                  remainingLow
                )}
                {" – "}
                {formatTime(
                  remainingHigh
                )}
              </div>
            )}

        </div>

      </section>


      {/* SESSION DETAILS */}
      <section className="section">

        <div className="section-header">

          <div>
            <div className="eyebrow">
              EXPERIMENT DETAILS
            </div>

            <h2>
              Dataset Information
            </h2>
          </div>

        </div>


        <div className="details">

          <div>
            <span>Session</span>
            <strong>
              {selectedSession || "--"}
            </strong>
          </div>

          <div>
            <span>Target Flow</span>
            <strong>
              {targetFlow
                ? `${targetFlow.toFixed(
                    1
                  )} mL/hr`
                : "--"}
            </strong>
          </div>

          <div>
            <span>Bag Volume</span>
            <strong>
              {bagVolume
                ? `${bagVolume.toFixed(
                    0
                  )} mL`
                : "--"}
            </strong>
          </div>

          <div>
            <span>Drop Factor</span>
            <strong>
              {dropFactor
                ? `${dropFactor.toFixed(
                    2
                  )} gtts/mL`
                : "--"}
            </strong>
          </div>

          <div>
            <span>EKF Windows</span>
            <strong>
              {fusionData.length}
            </strong>
          </div>

        </div>

      </section>


      {/* FOOTER */}
      <footer>

        <div>
          ⚠️
        </div>

        <p>
          <strong>
            Prototype / Research Use Only.
          </strong>{" "}
          This system uses synthetic validation
          data and is not a medical device. It
          must not be used for clinical decisions
          or to control infusion delivery.
        </p>

      </footer>

    </div>
  );
}

export default App;