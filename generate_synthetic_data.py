"""
Synthetic IV Drip Data Generator
==================================
Generates physics-grounded synthetic sensor data for a dual-sensor
(load cell + IR drop sensor) gravity IV infusion monitoring system.

Why physics-grounded, not pure random noise:
  A Kalman filter fusion model needs to be tested against data that
  resembles what real hardware would produce, not arbitrary numbers.
  This generator simulates the actual gravity-drip relationship and
  the two real, standardized drop-factor values used in hospitals
  (macrodrip 10/15/20 gtts/mL, microdrip 60 gtts/mL), then layers on
  realistic sensor-specific noise and drift.

IMPORTANT LIMITATION (be upfront about this with your faculty):
  Because both sensors here are simulated FROM the same underlying
  physics your Kalman filter will use to fuse them, strong filter
  performance on this data proves the filter correctly inverts a
  known model -- it does NOT prove the approach works on real noisy
  hardware. Real bench validation is a separate, later step.

Output: one CSV per simulated run, plus a manifest CSV listing all
runs and their ground-truth parameters (flow rate, drop factor, and
which anomaly type, if any, was injected).
"""

import numpy as np
import pandas as pd
import os
import json

# ----------------------------------------------------------------------
# Physical / clinical constants
# ----------------------------------------------------------------------

# Standardized IV tubing drop factors (drops per mL) actually used in
# hospitals. Macrodrip sets: 10, 15, 20 gtts/mL. Microdrip (pediatric/
# precision): 60 gtts/mL.
DROP_FACTORS = {
    "macrodrip_10": 10,
    "macrodrip_15": 15,
    "macrodrip_20": 20,
    "microdrip_60": 60,
}

# Approximate relative densities / viscosity multipliers for common IV
# fluids, used to perturb the *effective* drop factor slightly (denser/
# more viscous fluids form slightly different drop sizes than water).
FLUID_PROFILES = {
    "normal_saline": {"density_g_per_ml": 1.005, "viscosity_factor": 1.00},
    "d5w_dextrose":  {"density_g_per_ml": 1.020, "viscosity_factor": 1.05},
    "ringers_lactate": {"density_g_per_ml": 1.011, "viscosity_factor": 1.02},
}

SECONDS_PER_MIN = 60.0


def simulate_run(
    run_id: str,
    target_flow_ml_per_hr: float,
    drop_factor_name: str,
    fluid_name: str,
    bag_volume_ml: float = 500.0,
    duration_s: float = None,
    sample_period_s: float = 1.0,
    anomaly: str = "none",         # "none", "occlusion", "leak"
    anomaly_start_frac: float = 0.5,
    seed: int = None,
):
    """
    Simulate one gravity IV drip session, producing:
      - a load-cell weight-vs-time series (grams, sampled every sample_period_s)
      - an IR drop-sensor event series (timestamps of individual drops)
      - ground-truth true flow rate at every sample (for validation later)

    Physics model:
      True flow rate Q(t) [mL/hr] starts at target_flow_ml_per_hr and is
      held constant, except during an injected anomaly window:
        - "occlusion": Q(t) ramps down to ~15% of target (partial blockage)
        - "leak":      Q(t) ramps up to ~3x target (tubing disconnect / leak)
      Weight loss follows mass = volume * fluid_density, integrated from Q(t).
      Drop timing follows the *true* physical drop factor (drops/mL) for the
      selected tubing, with each drop's *observed* interval also affected by
      viscosity (which subtly changes real drop size vs. the nominal rating --
      this is the real-world effect your self-calibration loop is meant to
      correct for).

    Sensor noise model:
      - Load cell: small Gaussian jitter per sample + occasional larger
        "bump" spikes (vibration / bed movement), zero-mean so it doesn't
        bias the true mass trend.
      - IR drop sensor: each drop has a probability of being missed
        (under-count) or double-triggered (over-count), plus a slow drift
        in the *effective* drops/mL away from the nominal rated value,
        simulating real drop-factor drift with temperature/viscosity --
        this is what your calibration loop needs to detect and correct.

    Returns
    -------
    dict with keys: 'weight_df', 'drops_df', 'truth', 'meta'
    """
    rng = np.random.default_rng(seed)

    drop_factor_nominal = DROP_FACTORS[drop_factor_name]     # gtts/mL, as printed on tubing
    fluid = FLUID_PROFILES[fluid_name]
    density = fluid["density_g_per_ml"]
    visc = fluid["viscosity_factor"]

    if duration_s is None:
        hours_to_empty = bag_volume_ml / target_flow_ml_per_hr
        if anomaly == "none":
            # run long enough to actually fully drain the bag (with a small
            # buffer so natural noise doesn't leave a sliver unfinished)
            duration_s = 1.05 * hours_to_empty * 3600.0
        else:
            # anomaly runs: keep shorter, focused on the anomaly window itself
            # rather than waiting out a now much-slower drain time
            duration_s = 0.6 * hours_to_empty * 3600.0

    n_samples = int(duration_s // sample_period_s) + 1
    t = np.arange(n_samples) * sample_period_s   # seconds

    # ---- Ground truth flow-rate profile Q(t) in mL/hr ----
    Q = np.full(n_samples, target_flow_ml_per_hr, dtype=float)
    anomaly_start_idx = int(anomaly_start_frac * n_samples)

    if anomaly == "occlusion":
        # ramp down over ~2 minutes to 15% of target, stays there
        ramp_len = min(int(120 / sample_period_s), n_samples - anomaly_start_idx)
        ramp = np.linspace(1.0, 0.15, ramp_len)
        Q[anomaly_start_idx:anomaly_start_idx + ramp_len] *= ramp
        Q[anomaly_start_idx + ramp_len:] *= 0.15
    elif anomaly == "leak":
        # ramp up over ~30s to 3x target (fast, since a real disconnect is abrupt)
        ramp_len = min(int(30 / sample_period_s), n_samples - anomaly_start_idx)
        ramp = np.linspace(1.0, 3.0, ramp_len)
        Q[anomaly_start_idx:anomaly_start_idx + ramp_len] *= ramp
        Q[anomaly_start_idx + ramp_len:] *= 3.0

    # small natural variability even in the "normal" case (gravity IVs are
    # never perfectly constant -- patient movement, minor clamp settling)
    Q += rng.normal(0, target_flow_ml_per_hr * 0.01, size=n_samples)
    Q = np.clip(Q, 0, None)

    # ---- True cumulative volume infused -> true mass loss ----
    Q_ml_per_s = Q / 3600.0
    cum_volume_ml = np.concatenate(([0.0], np.cumsum(Q_ml_per_s[:-1]) * sample_period_s))
    cum_volume_ml = np.minimum(cum_volume_ml, bag_volume_ml)  # can't drain past empty
    true_mass_g = (bag_volume_ml - cum_volume_ml) * density   # remaining fluid mass

    # container/tubing tare weight (typical empty IV bag + residual ~30-40g)
    tare_g = 35.0
    true_weight_g = true_mass_g + tare_g

    # ---- Load cell sensor: true weight + noise ----
    jitter = rng.normal(0, 0.4, size=n_samples)                 # HX711-scale jitter, grams
    bump_mask = rng.random(n_samples) < 0.01                    # ~1% of samples get a bump
    bumps = np.where(bump_mask, rng.normal(0, 3.0, size=n_samples), 0.0)
    load_cell_weight_g = true_weight_g + jitter + bumps

    weight_df = pd.DataFrame({
        "t_s": t,
        "load_cell_weight_g": load_cell_weight_g,
        "true_weight_g": true_weight_g,       # ground truth, keep separate for validation only
        "true_flow_ml_per_hr": Q,
    })

    # ---- IR drop sensor: generate individual drop events ----
    # effective drop factor drifts slowly away from nominal due to viscosity/
    # temperature -- this is the real-world phenomenon the self-calibration
    # loop is supposed to track and correct.
    drift_amplitude = 0.08   # up to +/-8% drift over the run
    drift_curve = 1.0 + drift_amplitude * np.sin(2 * np.pi * t / max(t[-1], 1) * 0.7)
    effective_drop_factor_series = drop_factor_nominal * visc * drift_curve  # gtts/mL, time-varying TRUTH

    drop_times = []
    volume_accum = 0.0
    next_drop_volume = 1.0 / np.interp(0, t, effective_drop_factor_series)  # mL needed for next drop
    vol_so_far = 0.0
    idx = 0
    # integrate true volume flow to find when each drop "should" occur
    for i in range(1, n_samples):
        dv = Q_ml_per_s[i] * sample_period_s
        vol_so_far += dv
        eff_df_now = effective_drop_factor_series[i]
        ml_per_drop = 1.0 / eff_df_now
        while vol_so_far >= next_drop_volume:
            true_drop_time = t[i]  # approx to sample resolution
            drop_times.append(true_drop_time)
            next_drop_volume += ml_per_drop

    drop_times = np.array(drop_times)

    # sensor imperfection: missed drops (under-count) and false/double triggers
    miss_prob = 0.03
    double_prob = 0.02
    keep_mask = rng.random(len(drop_times)) > miss_prob
    observed_drop_times = drop_times[keep_mask].tolist()
    double_mask = rng.random(len(observed_drop_times)) < double_prob
    extra = [tm + rng.uniform(0.01, 0.05) for tm, is_double in zip(observed_drop_times, double_mask) if is_double]
    observed_drop_times = sorted(observed_drop_times + extra)
    # small timing jitter on each observed drop (IR detector isn't instantaneous)
    observed_drop_times = [tm + rng.normal(0, 0.02) for tm in observed_drop_times]

    drops_df = pd.DataFrame({
        "drop_time_s": observed_drop_times,
    })

    truth = pd.DataFrame({
        "t_s": t,
        "true_flow_ml_per_hr": Q,
        "true_weight_g": true_weight_g,
        "effective_drop_factor_gtts_per_ml": effective_drop_factor_series,
    })

    meta = {
        "run_id": run_id,
        "target_flow_ml_per_hr": target_flow_ml_per_hr,
        "drop_factor_name": drop_factor_name,
        "drop_factor_nominal_gtts_per_ml": drop_factor_nominal,
        "fluid_name": fluid_name,
        "bag_volume_ml": bag_volume_ml,
        "duration_s": duration_s,
        "sample_period_s": sample_period_s,
        "anomaly": anomaly,
        "anomaly_start_frac": anomaly_start_frac if anomaly != "none" else None,
        "n_weight_samples": n_samples,
        "n_drops_observed": len(observed_drop_times),
        "seed": seed,
    }

    return {"weight_df": weight_df, "drops_df": drops_df, "truth": truth, "meta": meta}


def build_dataset(out_dir="synthetic_dataset", n_normal_runs=12, n_occlusion_runs=4, n_leak_runs=4, base_seed=42):
    """
    Build a full synthetic dataset: a spread of normal runs across
    different flow rates / drop factors / fluids, plus anomaly runs
    for testing the disagreement / confidence-interval behavior.
    Writes one folder per run (weight.csv, drops.csv, truth.csv, meta.json)
    plus a manifest.csv indexing everything.
    """
    os.makedirs(out_dir, exist_ok=True)
    manifest_rows = []
    rng = np.random.default_rng(base_seed)

    flow_rates = [50, 75, 100, 125, 150]           # mL/hr, common clinical range
    drop_factor_names = list(DROP_FACTORS.keys())
    fluid_names = list(FLUID_PROFILES.keys())

    def make_run(i, anomaly):
        run_id = f"run_{i:03d}_{anomaly}"
        flow = float(rng.choice(flow_rates))
        dfn = str(rng.choice(drop_factor_names))
        fluid = str(rng.choice(fluid_names))
        seed = int(rng.integers(0, 1_000_000))
        result = simulate_run(
            run_id=run_id,
            target_flow_ml_per_hr=flow,
            drop_factor_name=dfn,
            fluid_name=fluid,
            anomaly=anomaly,
            seed=seed,
        )
        run_dir = os.path.join(out_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        result["weight_df"].to_csv(os.path.join(run_dir, "weight_sensor.csv"), index=False)
        result["drops_df"].to_csv(os.path.join(run_dir, "drop_sensor.csv"), index=False)
        result["truth"].to_csv(os.path.join(run_dir, "ground_truth.csv"), index=False)
        with open(os.path.join(run_dir, "meta.json"), "w") as f:
            json.dump(result["meta"], f, indent=2)
        manifest_rows.append(result["meta"])
        return result

    for i in range(n_normal_runs):
        make_run(i, "none")
    for i in range(n_normal_runs, n_normal_runs + n_occlusion_runs):
        make_run(i, "occlusion")
    for i in range(n_normal_runs + n_occlusion_runs, n_normal_runs + n_occlusion_runs + n_leak_runs):
        make_run(i, "leak")

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(os.path.join(out_dir, "manifest.csv"), index=False)
    print(f"Generated {len(manifest_rows)} runs into '{out_dir}/'")
    print(manifest[["run_id", "target_flow_ml_per_hr", "drop_factor_name", "fluid_name", "anomaly"]].to_string(index=False))
    return manifest


if __name__ == "__main__":
    build_dataset()
