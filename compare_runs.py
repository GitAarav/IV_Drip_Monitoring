"""
Live "what if I change this?" comparison tool
================================================
Use this in front of your faculty. Change ONE setting at the top,
run the script, and it produces a before/after plot showing exactly
how that change affects the simulated IV session.

This does NOT need the pre-generated synthetic_dataset folder --
it generates fresh runs on the spot using generate_synthetic_data.py,
so you can change numbers live and immediately show a new result.

HOW TO USE IN THE DEMO:
  1. Pick ONE thing to change from the list of examples below.
  2. Edit the two settings dicts (RUN_A = "before", RUN_B = "after").
  3. Run: python3 compare_runs.py
  4. It saves a plot: comparison_output.png -- show that.

EXAMPLES OF "WHAT IF I CHANGE THIS" YOU CAN DEMO LIVE:
  - Change target_flow_ml_per_hr (e.g. 50 vs 150)
      -> shows the weight line getting steeper/shallower, and the
         drop rate getting faster/slower. Proves the generator
         responds to clinically realistic flow settings.
  - Change drop_factor_name (e.g. "macrodrip_15" vs "microdrip_60")
      -> shows drop COUNT changing a lot even though the FLUID
         VOLUME flow is the same -- because drop factor is drops
         per mL, a 60 gtts/mL tube produces 4x more drops than a
         15 gtts/mL tube for the same fluid volume. Good one to
         explain the physical meaning of "drop factor."
  - Change anomaly from "none" to "occlusion" or "leak"
      -> shows the flow-rate line suddenly dropping (occlusion) or
         spiking (leak) partway through. This is the scenario your
         Kalman filter's confidence interval is supposed to react to.
  - Change fluid_name (e.g. "normal_saline" vs "d5w_dextrose")
      -> shows a SMALL shift in the weight curve's slope, because
         different fluids have slightly different density -- subtle
         but real, good for showing you modeled fluid properties
         rather than treating "IV fluid" as one generic liquid.
  - Change seed (any different integer)
      -> everything else stays the same, but the exact noise pattern
         changes -- good for showing "this isn't the same canned
         output every time, it's genuinely randomized within the
         physics constraints."
"""

import matplotlib.pyplot as plt
from generate_synthetic_data import simulate_run

# ----------------------------------------------------------------------
# EDIT THESE TWO SETTINGS TO SHOW A "BEFORE vs AFTER" CHANGE
# Keep everything the same except the ONE thing you want to demonstrate.
# ----------------------------------------------------------------------

RUN_A = dict(
    run_id="demo_A",
    target_flow_ml_per_hr=100.0,
    drop_factor_name="macrodrip_15",
    fluid_name="normal_saline",
    anomaly="none",
    duration_s=3600,          # 1 hour, kept short for a fast live demo
    seed=1,
)

RUN_B = dict(
    run_id="demo_B",
    target_flow_ml_per_hr=100.0,
    drop_factor_name="macrodrip_15",
    fluid_name="normal_saline",
    anomaly="occlusion",      # <-- the ONE change: injected occlusion
    anomaly_start_frac=0.5,
    duration_s=3600,
    seed=1,
)

# ----------------------------------------------------------------------

def run_and_plot(a_settings, b_settings, label_a="A (before)", label_b="B (after change)"):
    result_a = simulate_run(**a_settings)
    result_b = simulate_run(**b_settings)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))

    wa, wb = result_a["weight_df"], result_b["weight_df"]
    da, db = result_a["drops_df"], result_b["drops_df"]

    # Weight over time
    axes[0, 0].plot(wa.t_s/60, wa.load_cell_weight_g, label=label_a)
    axes[0, 0].plot(wb.t_s/60, wb.load_cell_weight_g, label=label_b)
    axes[0, 0].set_title("Load cell weight over time")
    axes[0, 0].set_xlabel("minutes"); axes[0, 0].set_ylabel("grams"); axes[0, 0].legend()

    # True flow rate over time (the ground-truth signal driving everything)
    axes[0, 1].plot(wa.t_s/60, wa.true_flow_ml_per_hr, label=label_a)
    axes[0, 1].plot(wb.t_s/60, wb.true_flow_ml_per_hr, label=label_b)
    axes[0, 1].set_title("True flow rate over time")
    axes[0, 1].set_xlabel("minutes"); axes[0, 1].set_ylabel("mL/hr"); axes[0, 1].legend()

    # Drop count per 30s bin
    import numpy as np
    bins_a = np.arange(0, wa.t_s.max()+30, 30)
    counts_a, _ = np.histogram(da.drop_time_s, bins=bins_a)
    bins_b = np.arange(0, wb.t_s.max()+30, 30)
    counts_b, _ = np.histogram(db.drop_time_s, bins=bins_b)
    axes[1, 0].bar(bins_a[:-1]/60, counts_a, width=0.3, alpha=0.6, label=label_a)
    axes[1, 0].bar(bins_b[:-1]/60, counts_b, width=0.3, alpha=0.6, label=label_b)
    axes[1, 0].set_title("Drop count per 30s bin")
    axes[1, 0].set_xlabel("minutes"); axes[1, 0].set_ylabel("drops/30s"); axes[1, 0].legend()

    # Summary numbers as text
    axes[1, 1].axis("off")
    summary = (
        f"{label_a}\n"
        f"  flow: {a_settings.get('target_flow_ml_per_hr')} mL/hr\n"
        f"  drop factor: {a_settings.get('drop_factor_name')}\n"
        f"  fluid: {a_settings.get('fluid_name')}\n"
        f"  anomaly: {a_settings.get('anomaly', 'none')}\n"
        f"  total drops observed: {len(da)}\n\n"
        f"{label_b}\n"
        f"  flow: {b_settings.get('target_flow_ml_per_hr')} mL/hr\n"
        f"  drop factor: {b_settings.get('drop_factor_name')}\n"
        f"  fluid: {b_settings.get('fluid_name')}\n"
        f"  anomaly: {b_settings.get('anomaly', 'none')}\n"
        f"  total drops observed: {len(db)}\n"
    )
    axes[1, 1].text(0.02, 0.98, summary, va="top", fontsize=10, family="monospace")

    plt.tight_layout()
    plt.savefig("comparison_output.png", dpi=110)
    print("Saved comparison_output.png")


if __name__ == "__main__":
    run_and_plot(RUN_A, RUN_B)
