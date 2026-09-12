"""
RUN THIS FILE to see the Kalman filter in action with accuracy numbers.
=========================================================================
This is the script you run in VS Code and show your faculty. It:
  1. Loads one simulated run (weight_sensor.csv + drop_sensor.csv)
  2. Runs the Kalman filter fusion (kalman_filter_iv.py)
  3. Compares the fused estimate against:
       - load-cell-only baseline
       - drop-sensor-only baseline
       - the true ground-truth flow rate (only used for GRADING, never
         given to the filter itself)
  4. Prints real accuracy numbers (MAE = Mean Absolute Error, lower is
     better) for all three approaches side by side
  5. Computes a remaining-time-with-confidence-interval estimate at
     several points in the run
  6. Saves a plot you can show on screen

HOW TO RUN IN VS CODE:
  1. Open this whole "iv_sim" folder in VS Code (File > Open Folder).
  2. Open a terminal inside VS Code (Terminal > New Terminal).
  3. Make sure the packages are installed (only needed once):
         pip install numpy pandas matplotlib
  4. Run:
         python run_demo.py
     (or python3 run_demo.py depending on your system)
  5. Watch the terminal for the printed accuracy table, and open the
     saved "demo_output.png" file (VS Code will preview it if you
     click it in the file explorer) to show the plots.
  6. To show a DIFFERENT run (e.g. an occlusion case instead of normal),
     change RUN_DIR near the top of this file to point at a different
     folder inside synthetic_dataset/, save, and run again.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from kalman_filter_iv import run_fusion

# ----------------------------------------------------------------------
# CHANGE THIS to point at any run folder to demo a different scenario
# ----------------------------------------------------------------------
RUN_DIR = "synthetic_dataset/run_005_none"      # a clean, no-anomaly run
# RUN_DIR = "synthetic_dataset/run_005_none"  # try this one too
# RUN_DIR = "synthetic_dataset/run_016_leak"

WINDOW_S = 60.0          # how many seconds of data go into each fused estimate
FLUID_DENSITY = 1.01     # g/mL, approx for common IV fluids


def compute_mae(pred, true):
    return float(np.mean(np.abs(np.array(pred) - np.array(true))))


def compute_rmse(pred, true):
    return float(np.sqrt(np.mean((np.array(pred) - np.array(true)) ** 2)))


def main():
    print(f"Running Kalman filter fusion on: {RUN_DIR}\n")

    results, meta = run_fusion(RUN_DIR, window_s=WINDOW_S, fluid_density=FLUID_DENSITY, verbose=True)

    print(f"\nRun settings: target flow={meta['target_flow_ml_per_hr']} mL/hr, "
          f"tubing={meta['drop_factor_name']}, fluid={meta['fluid_name']}, "
          f"anomaly={meta['anomaly']}")
    print(f"Total fused estimates produced: {len(results)}\n")

    # ---- ACCURACY COMPARISON ----
    mae_fused = compute_mae(results.fused_flow_ml_per_hr, results.true_flow)
    mae_weight_only = compute_mae(results.weight_only_flow, results.true_flow)
    mae_drop_only = compute_mae(results.drop_only_flow, results.true_flow)

    rmse_fused = compute_rmse(results.fused_flow_ml_per_hr, results.true_flow)
    rmse_weight_only = compute_rmse(results.weight_only_flow, results.true_flow)
    rmse_drop_only = compute_rmse(results.drop_only_flow, results.true_flow)

    print("=" * 60)
    print("ACCURACY COMPARISON (flow rate estimate vs true flow rate)")
    print("=" * 60)
    print(f"{'Method':<25}{'MAE (mL/hr)':>15}{'RMSE (mL/hr)':>15}")
    print(f"{'Load cell only':<25}{mae_weight_only:>15.2f}{rmse_weight_only:>15.2f}")
    print(f"{'Drop sensor only':<25}{mae_drop_only:>15.2f}{rmse_drop_only:>15.2f}")
    print(f"{'Kalman fusion (ours)':<25}{mae_fused:>15.2f}{rmse_fused:>15.2f}")
    print("=" * 60)

    # ---- DROP FACTOR CALIBRATION CHECK ----
    final_estimated_k = results.fused_drop_factor.iloc[-1]
    final_true_k = results.true_drop_factor.iloc[-1]
    nominal_k = meta["drop_factor_nominal_gtts_per_ml"]
    print(f"\nDrop factor self-calibration:")
    print(f"  Nominal (printed on tubing): {nominal_k:.2f} gtts/mL")
    print(f"  True effective value (end of run): {final_true_k:.2f} gtts/mL")
    print(f"  Filter's estimate (end of run):    {final_estimated_k:.2f} gtts/mL")
    print(f"  (If the filter's estimate is closer to the TRUE value than the")
    print(f"   NOMINAL value is, the self-calibration is working.)")

    # ---- REMAINING TIME + CONFIDENCE INTERVAL, sampled at a few points ----
    print(f"\nRemaining-time predictions with confidence interval (sampled points):")
    bag_volume_ml = meta["bag_volume_ml"]
    # need cumulative volume infused so far to know what's left -- approximate
    # using integrated fused flow rate (trapezoidal) up to each sample point
    dt_hr = WINDOW_S / 3600.0
    cum_vol = np.cumsum(results.fused_flow_ml_per_hr * dt_hr)
    remaining_vol = np.maximum(bag_volume_ml - cum_vol, 0)

    sample_idxs = np.linspace(2, len(results) - 1, 5).astype(int)
    for idx in sample_idxs:
        Q = results.fused_flow_ml_per_hr.iloc[idx]
        Q_std = results.fused_flow_std.iloc[idx]
        rem_vol = remaining_vol[idx]
        if Q <= 1e-3:
            continue
        est_time_min = (rem_vol / Q) * 60
        # propagate uncertainty: wider std on Q -> wider time range (simple
        # approximation using +/-1 std on Q, clipped to avoid divide-by-zero)
        Q_low = max(Q - Q_std, 1.0)
        Q_high = Q + Q_std
        t_low = (rem_vol / Q_high) * 60
        t_high = (rem_vol / Q_low) * 60
        t_min = results.t_mid_s.iloc[idx] / 60
        print(f"  at {t_min:5.1f} min: estimate {est_time_min:5.1f} min remaining  "
              f"(range: {t_low:5.1f}-{t_high:5.1f} min, flow std={Q_std:4.1f} mL/hr)")

    # ---- PLOT ----
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))

    axes[0, 0].plot(results.t_mid_s/60, results.true_flow, "k--", label="TRUE flow (ground truth)", linewidth=2)
    axes[0, 0].plot(results.t_mid_s/60, results.weight_only_flow, alpha=0.5, label="Load cell only")
    axes[0, 0].plot(results.t_mid_s/60, results.drop_only_flow, alpha=0.5, label="Drop sensor only")
    axes[0, 0].plot(results.t_mid_s/60, results.fused_flow_ml_per_hr, label="Kalman fusion", linewidth=2)
    axes[0, 0].set_title("Flow rate estimate: fusion vs single sensors vs truth")
    axes[0, 0].set_xlabel("minutes"); axes[0, 0].set_ylabel("mL/hr"); axes[0, 0].legend(fontsize=8)

    axes[0, 1].plot(results.t_mid_s/60, results.true_drop_factor, "k--", label="TRUE drop factor", linewidth=2)
    axes[0, 1].axhline(nominal_k, color="gray", linestyle=":", label="Nominal (fixed) assumption")
    axes[0, 1].plot(results.t_mid_s/60, results.fused_drop_factor, label="Filter's estimate", linewidth=2)
    axes[0, 1].set_title("Drop factor: self-calibration over time")
    axes[0, 1].set_xlabel("minutes"); axes[0, 1].set_ylabel("gtts/mL"); axes[0, 1].legend(fontsize=8)

    axes[1, 0].fill_between(results.t_mid_s/60,
                             results.fused_flow_ml_per_hr - results.fused_flow_std,
                             results.fused_flow_ml_per_hr + results.fused_flow_std,
                             alpha=0.3, label="uncertainty band (+/- 1 std)")
    axes[1, 0].plot(results.t_mid_s/60, results.fused_flow_ml_per_hr, label="fused estimate")
    axes[1, 0].plot(results.t_mid_s/60, results.true_flow, "k--", label="true flow", linewidth=1)
    axes[1, 0].set_title("Confidence band on flow estimate\n(should widen during anomalies)")
    axes[1, 0].set_xlabel("minutes"); axes[1, 0].set_ylabel("mL/hr"); axes[1, 0].legend(fontsize=8)

    axes[1, 1].axis("off")
    summary_text = (
        f"Run: {meta['run_id']}\n"
        f"Target flow: {meta['target_flow_ml_per_hr']} mL/hr\n"
        f"Tubing: {meta['drop_factor_name']}\n"
        f"Fluid: {meta['fluid_name']}\n"
        f"Anomaly: {meta['anomaly']}\n\n"
        f"MAE (mL/hr), lower = better:\n"
        f"  Load cell only:   {mae_weight_only:.2f}\n"
        f"  Drop sensor only: {mae_drop_only:.2f}\n"
        f"  Kalman fusion:    {mae_fused:.2f}\n"
    )
    axes[1, 1].text(0.02, 0.98, summary_text, va="top", fontsize=11, family="monospace")

    plt.tight_layout()
    plt.savefig("demo_output.png", dpi=110)
    print(f"\nSaved plot to demo_output.png")


if __name__ == "__main__":
    main()
