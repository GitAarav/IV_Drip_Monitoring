import React, { useEffect, useState } from "react";

import {
  Activity,
  Droplets,
  Clock,
  Wifi,
  Scale,
  Radio,
  BrainCircuit,
  AlertTriangle,
} from "lucide-react";

import MetricCard from "./components/MetricCard";
import SensorCard from "./components/SensorCard";
import PredictionCard from "./components/PredictionCard";
import FlowChart from "./components/FlowChart";
import WeightChart from "./components/WeightChart";

import {
  initialData,
  generateHistory,
} from "./data/mockData";

import "./App.css";

function App() {

  const [data, setData] = useState(initialData);
  const [history, setHistory] = useState(generateHistory());

  /*
   * Simple simulation.
   * Later this can be replaced with:
   *
   * fetch()
   * WebSocket
   * FastAPI
   * MQTT
   * ESP32 data
   */

  useEffect(() => {

    const interval = setInterval(() => {

      setData((previous) => {

        const newWeight =
          previous.currentWeight - 0.8;

        const loadCellFlow =
          previous.loadCellFlow +
          (Math.random() - 0.5) * 1.5;

        const irFlow =
          previous.irFlow +
          (Math.random() - 0.5) * 2;

        const fusedFlow =
          (loadCellFlow + irFlow) / 2;

        const difference =
          Math.abs(loadCellFlow - irFlow);

        const remainingFluid =
          Math.max(newWeight, 0);

        const remainingTime =
          fusedFlow > 0
            ? (remainingFluid / fusedFlow) * 60
            : 0;

        return {
          ...previous,

          currentWeight:
            Number(newWeight.toFixed(1)),

          remainingFluid:
            Number(remainingFluid.toFixed(1)),

          loadCellFlow:
            Number(loadCellFlow.toFixed(1)),

          irFlow:
            Number(irFlow.toFixed(1)),

          fusedFlow:
            Number(fusedFlow.toFixed(1)),

          sensorDifference:
            Number(difference.toFixed(1)),

          remainingTime:
            Math.round(remainingTime),

          confidence:
            difference < 5
              ? 94
              : difference < 10
                ? 82
                : 65,

          status:
            difference > 10
              ? "WARNING"
              : "NORMAL",
        };
      });

    }, 2000);

    return () => clearInterval(interval);

  }, []);

  useEffect(() => {

    setHistory((previous) => {

      const next = [
        ...previous,
        {
          time: `${previous.length} min`,
          weight: data.currentWeight,
          loadCell: data.loadCellFlow,
          ir: data.irFlow,
          fused: data.fusedFlow,
        },
      ];

      return next.slice(-30);
    });

  }, [
    data.currentWeight,
    data.fusedFlow,
  ]);

  return (

    <div className="app">

      {/* SIDEBAR */}

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-icon">
            <Droplets size={24} />
          </div>

          <div>
            <div className="brand-title">
              IV Monitor
            </div>

            <div className="brand-subtitle">
              Predictive System
            </div>
          </div>

        </div>

        <nav>

          <div className="nav-item active">
            <Activity size={18} />
            Dashboard
          </div>

          <div className="nav-item">
            <Clock size={18} />
            Live Monitor
          </div>

          <div className="nav-item">
            <Scale size={18} />
            Sensor Fusion
          </div>

          <div className="nav-item">
            <AlertTriangle size={18} />
            Alerts
          </div>

          <div className="nav-item">
            <Wifi size={18} />
            Devices
          </div>

        </nav>

        <div className="sidebar-footer">
          Research Prototype
        </div>

      </aside>


      {/* MAIN */}

      <main className="main">

        <header className="topbar">

          <div>
            <h1>
              Predictive IV Monitoring
            </h1>

            <p>
              Dual-sensor infusion monitoring and
              remaining-time prediction
            </p>
          </div>

          <div className="live-status">
            <span className="live-dot" />
            SIMULATION LIVE
          </div>

        </header>


        {/* INFO BAR */}

        <div className="session-bar">

          <div>
            <strong>
              {data.deviceId}
            </strong>

            <span>
              {data.bedId}
            </span>

            <span>
              {data.fluidType}
            </span>
          </div>

          <div className="normal-status">
            ● {data.status}
          </div>

        </div>


        {/* METRICS */}

        <section className="metrics">

          <MetricCard
            title="Current Flow"
            value={`${data.fusedFlow} mL/hr`}
            subtitle="EKF fused estimate"
            icon={<Activity size={20} />}
          />

          <MetricCard
            title="Remaining Fluid"
            value={`${data.remainingFluid} mL`}
            subtitle="Estimated from bag weight"
            icon={<Droplets size={20} />}
          />

          <MetricCard
            title="Bag Weight"
            value={`${data.currentWeight} g`}
            subtitle={`Initial ${data.initialWeight} g`}
            icon={<Scale size={20} />}
          />

          <MetricCard
            title="Device"
            value="Online"
            subtitle="ESP32 connection"
            icon={<Wifi size={20} />}
          />

        </section>


        {/* PREDICTION */}

        <section className="prediction-layout">

          <PredictionCard
            remainingTime={data.remainingTime}
            confidence={data.confidence}
          />

          <div className="sensor-overview">

            <div className="section-heading">
              <div>
                <h2>
                  Sensor Fusion
                </h2>

                <p>
                  Independent measurements combined
                  using EKF
                </p>
              </div>

              <BrainCircuit size={28} />
            </div>

            <div className="sensor-grid">

              <SensorCard
                title="Load Cell"
                value={data.loadCellFlow}
                unit=" mL/hr"
                description="Weight-loss derived flow"
              />

              <SensorCard
                title="IR Drop Sensor"
                value={data.irFlow}
                unit=" mL/hr"
                description="Optical drop-derived flow"
              />

              <SensorCard
                title="EKF Fusion"
                value={data.fusedFlow}
                unit=" mL/hr"
                description="Fused flow estimate"
              />

            </div>

            <div className="agreement">

              <div>
                <strong>
                  Sensor Agreement
                </strong>

                <p>
                  Difference between independent
                  measurements
                </p>
              </div>

              <div className={
                data.sensorDifference > 10
                  ? "agreement-warning"
                  : "agreement-good"
              }>
                {data.sensorDifference > 10
                  ? "LOW"
                  : "HIGH"}
              </div>

            </div>

          </div>

        </section>


        {/* CHARTS */}

        <section className="charts">

          <FlowChart data={history} />

          <WeightChart data={history} />

        </section>


        {/* CALIBRATION */}

        <section className="bottom-grid">

          <div className="info-card">

            <div className="info-card-header">
              <h2>
                Adaptive Calibration
              </h2>

              <Radio size={22} />
            </div>

            <div className="calibration-row">

              <span>
                Estimated Drop Factor
              </span>

              <strong>
                {data.dropFactor} gtts/mL
              </strong>

            </div>

            <div className="calibration-row">

              <span>
                Reference
              </span>

              <strong>
                Load Cell
              </strong>

            </div>

            <div className="calibration-status">
              ● ADAPTIVE ESTIMATION ACTIVE
            </div>

          </div>


          <div className="info-card">

            <div className="info-card-header">

              <h2>
                Prediction Uncertainty
              </h2>

              <Activity size={22} />

            </div>

            <div className="uncertainty-value">
              ± {data.flowUncertainty} mL/hr
            </div>

            <p>
              Current uncertainty in the fused flow
              estimate.
            </p>

            <div className="uncertainty-bar">
              <div
                style={{
                  width: `${Math.min(
                    data.confidence,
                    100
                  )}%`,
                }}
              />
            </div>

            <strong>
              {data.confidence}% confidence
            </strong>

          </div>

        </section>


        {/* DISCLAIMER */}

        <footer className="disclaimer">

          Research prototype for academic demonstration.
          This system monitors and predicts infusion state;
          it does not control infusion flow and is not a
          replacement for clinical infusion equipment.

        </footer>

      </main>

    </div>
  );
}

export default App;