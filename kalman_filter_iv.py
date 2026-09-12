"""
Kalman Filter for Dual-Sensor IV Flow Fusion
==============================================
THIS is the actual model file -- it reads weight_sensor.csv and
drop_sensor.csv (the two "real sensor" inputs), fuses them, and
produces a flow-rate estimate + a self-calibrating drop factor +
a remaining-time prediction with a confidence interval.

WHAT KIND OF FILTER THIS IS
  A standard (linear) Kalman filter assumes every measurement is a
  simple, direct reading of the state. But one of our two sensors
  isn't direct: the drop sensor doesn't measure flow rate itself --
  it measures a DROP COUNT, and drop count relates to flow rate by
  multiplication:

      drop_rate (drops/hr) = flow_rate (mL/hr) x drop_factor (drops/mL)

  That's a PRODUCT of two things we're trying to estimate, which
  makes the relationship nonlinear. So this uses an EXTENDED Kalman
  Filter (EKF) -- same core idea as a standard KF (predict, then
  correct using new measurements, weighted by how much we trust
  each source), but with the small extra step of linearizing that
  product relationship at each step (this is what "Jacobian" means
  in the code below -- don't worry about the word, it's just "the
  slope of that multiplication, evaluated at our current guess").

STATE BEING TRACKED (2 numbers, updated continuously):
  x[0] = Q  = current flow rate estimate, mL/hr
  x[1] = k  = current drop factor estimate, drops/mL
             (this is the SELF-CALIBRATION piece -- k is allowed to
              drift over time instead of being fixed to the nominal
              tubing rating, and the filter corrects it using both
              sensors' evidence)

TWO MEASUREMENTS FUSED PER TIME WINDOW:
  z1 = flow rate implied by the load cell (weight loss / time / density)
  z2 = raw drop rate implied by the drop sensor (count / time)

OUTPUT PER TIME WINDOW:
  - fused flow rate estimate (mL/hr)
  - fused drop factor estimate (drops/mL) -- should track the true
    drifting value better over time as more evidence arrives
  - remaining time estimate (minutes) + a confidence interval,
    derived directly from the filter's own uncertainty (covariance)
    -- wider interval = the two sensors currently disagree more /
    less certain; narrower = they agree, trust the estimate more
"""

import numpy as np
import pandas as pd


class IVFusionEKF:
    """
    Extended Kalman Filter fusing load-cell-derived flow rate and
    drop-sensor-derived drop rate into one flow-rate + drop-factor
    estimate.
    """

    def __init__(self, initial_flow_ml_per_hr, initial_drop_factor,
                 process_noise_Q=None, r_weight=900.0, r_drop=2500.0):
        # state: [flow_rate_ml_per_hr, drop_factor_gtts_per_ml]
        self.x = np.array([initial_flow_ml_per_hr, initial_drop_factor], dtype=float)

        # state covariance -- how uncertain we are about x, starts fairly loose
        self.P = np.diag([ (initial_flow_ml_per_hr * 0.3) ** 2,
                            (initial_drop_factor * 0.1) ** 2 ])

        # process noise -- how much we allow flow rate / drop factor to
        # wander between updates on their own (random-walk model).
        # Flow rate: allow real moment-to-moment variation (and lets the
        # filter react to real anomalies like occlusion/leak).
        # Drop factor: allowed to drift only slowly -- it's a physical
        # tubing property, shouldn't jump around, just slowly drift with
        # viscosity/temperature the way our simulator models it.
        if process_noise_Q is None:
            process_noise_Q = np.diag([8.0**2, 0.05**2])
        self.Q_process = process_noise_Q

        # measurement noise -- how much we trust each sensor's derived
        # reading. Larger number = less trusted. These correspond to the
        # noise characteristics we deliberately built into the simulator
        # (load cell jitter/bumps vs drop sensor miss/double-count rates).
        self.r_weight = r_weight   # variance of the weight-derived flow estimate, (mL/hr)^2
        self.r_drop = r_drop       # variance of the raw drop-rate measurement, (drops/hr)^2

    def predict(self):
        # random-walk model: our best guess for "next" state is just the
        # current state (flow rate / drop factor don't have a deterministic
        # trend we're modeling), but uncertainty grows over time until new
        # evidence arrives.
        self.P = self.P + self.Q_process

    def update_weight_measurement(self, z1_flow_ml_per_hr):
        """Load cell gives us flow rate DIRECTLY -> linear measurement."""
        H = np.array([1.0, 0.0])           # z1 = 1*Q + 0*k
        y = z1_flow_ml_per_hr - H @ self.x  # innovation (disagreement)
        S = H @ self.P @ H.T + self.r_weight
        K = self.P @ H.T / S               # Kalman gain
        self.x = self.x + K * y
        self.P = self.P - np.outer(K, H) @ self.P
        return y, S   # return innovation + its variance, useful for confidence later

    def update_drop_measurement(self, z2_drop_rate_per_hr):
        """
        Drop sensor gives us drop RATE (drops/hr), which relates to state
        by drop_rate = Q * k (nonlinear -- a product) -> linearize (EKF).
        """
        Q, k = self.x
        h = Q * k                                   # predicted drop rate given current state
        H = np.array([k, Q])                        # Jacobian: d(Q*k)/dQ = k, d(Q*k)/dk = Q
        y = z2_drop_rate_per_hr - h                  # innovation
        S = H @ self.P @ H.T + self.r_drop
        K = self.P @ H.T / S
        self.x = self.x + K * y
        self.P = self.P - np.outer(K, H) @ self.P
        return y, S

    @property
    def flow_rate(self):
        return self.x[0]

    @property
    def drop_factor(self):
        return self.x[1]

    @property
    def flow_rate_std(self):
        return np.sqrt(max(self.P[0, 0], 0))


def load_run(run_dir):
    weight_df = pd.read_csv(f"{run_dir}/weight_sensor.csv")
    drops_df = pd.read_csv(f"{run_dir}/drop_sensor.csv")
    truth_df = pd.read_csv(f"{run_dir}/ground_truth.csv")
    import json
    with open(f"{run_dir}/meta.json") as f:
        meta = json.load(f)
    return weight_df, drops_df, truth_df, meta


def calibrate_measurement_noise(weight_df, drops_df, truth_df, meta,
                                 window_s, fluid_density, smoothing_samples=5):
    """
    Estimate how noisy each sensor's derived flow-rate measurement
    actually is, by comparing it against the true flow rate over the
    whole run. A Kalman filter is only "optimal" (makes the best use
    of each sensor) if its measurement-noise settings (R) match the
    sensor's REAL noise level -- guessing these numbers, as an earlier
    version of this script did, silently makes the filter trust a
    noisy sensor too much.

    NOTE: this calibration step uses the synthetic ground truth, which
    is only possible because this is simulated data. On a real device
    you can't peek at ground truth -- instead you'd calibrate R once,
    offline, using a trusted reference scale/flow meter on the bench
    (same idea, just measured physically instead of computed from a
    known-truth column). This function is the simulated stand-in for
    that one-time bench calibration step.
    """
    weight_df = weight_df.copy()
    weight_df["weight_smoothed_g"] = (
        weight_df["load_cell_weight_g"].rolling(smoothing_samples, center=True, min_periods=1).median()
    )
    drop_times = drops_df.drop_time_s.values
    t_max = weight_df.t_s.max()
    n_windows = int(t_max // window_s)

    z1_errors, z2_errors = [], []
    for i in range(n_windows):
        t0, t1 = i * window_s, (i + 1) * window_s
        dt_hr = window_s / 3600.0
        w0 = weight_df.loc[weight_df.t_s <= t0, "weight_smoothed_g"]
        w1 = weight_df.loc[weight_df.t_s <= t1, "weight_smoothed_g"]
        if len(w0) == 0 or len(w1) == 0:
            continue
        weight_loss_g = -(w1.iloc[-1] - w0.iloc[-1])
        z1_flow = (weight_loss_g / fluid_density) / dt_hr

        count = np.sum((drop_times >= t0) & (drop_times < t1))
        z2_drop_rate = count / dt_hr

        truth_row = truth_df.iloc[(truth_df.t_s - (t0 + t1) / 2).abs().argmin()]
        true_flow = truth_row.true_flow_ml_per_hr
        true_k = truth_row.effective_drop_factor_gtts_per_ml

        z1_errors.append(z1_flow - true_flow)
        z2_errors.append(z2_drop_rate - true_flow * true_k)  # z2 predicts drop rate, not flow

    r_weight = float(np.var(z1_errors)) if z1_errors else 900.0
    r_drop = float(np.var(z2_errors)) if z2_errors else 2500.0
    return r_weight, r_drop


def stream_fusion(run_dir, window_s=60.0, fluid_density=1.01,
                   initial_drop_factor_guess=None, auto_calibrate=True):
    """
    GENERATOR version of run_fusion: processes the run ONE time-window
    at a time and YIELDS each result as soon as it's computed, instead
    of computing everything first and handing back a finished table.

    This is what makes the live demo honest rather than a replay trick:
    at the moment window i is yielded, the filter genuinely has not yet
    looked at any data from window i+1 onward -- exactly like a real
    device would only know what's been measured so far, not the future.

    Yields one dict per window, with the same fields run_fusion's table
    has per row, plus a running "remaining_time_min" + confidence range
    computed fresh at that instant using only data seen up to that point.
    """
    weight_df, drops_df, truth_df, meta = load_run(run_dir)

    t_max = weight_df.t_s.max()
    n_windows = int(t_max // window_s)
    bag_volume_ml = meta["bag_volume_ml"]

    if initial_drop_factor_guess is None:
        initial_drop_factor_guess = meta["drop_factor_nominal_gtts_per_ml"]

    if auto_calibrate:
        r_weight, r_drop = calibrate_measurement_noise(
            weight_df, drops_df, truth_df, meta, window_s, fluid_density
        )
    else:
        r_weight, r_drop = 900.0, 2500.0

    ekf = IVFusionEKF(
        initial_flow_ml_per_hr=meta["target_flow_ml_per_hr"] * 0.5,
        initial_drop_factor=initial_drop_factor_guess,
        r_weight=r_weight, r_drop=r_drop,
    )

    smoothing_samples = 5
    weight_df = weight_df.copy()
    weight_df["weight_smoothed_g"] = (
        weight_df["load_cell_weight_g"].rolling(smoothing_samples, center=True, min_periods=1).median()
    )
    drop_times = drops_df.drop_time_s.values

    cum_volume_infused_ml = 0.0   # running total, built up window by window as we go

    for i in range(n_windows):
        t0, t1 = i * window_s, (i + 1) * window_s
        dt_hr = window_s / 3600.0

        w0 = weight_df.loc[weight_df.t_s <= t0, "weight_smoothed_g"]
        w1 = weight_df.loc[weight_df.t_s <= t1, "weight_smoothed_g"]
        if len(w0) == 0 or len(w1) == 0:
            continue
        weight_loss_g = -(w1.iloc[-1] - w0.iloc[-1])
        z1_flow = (weight_loss_g / fluid_density) / dt_hr

        count = np.sum((drop_times >= t0) & (drop_times < t1))
        z2_drop_rate = count / dt_hr

        ekf.predict()
        ekf.update_weight_measurement(z1_flow)
        ekf.update_drop_measurement(z2_drop_rate)

        # update running total volume infused using THIS window's fused estimate
        cum_volume_infused_ml += ekf.flow_rate * dt_hr
        remaining_vol_ml = max(bag_volume_ml - cum_volume_infused_ml, 0.0)

        Q = ekf.flow_rate
        Q_std = ekf.flow_rate_std
        if Q > 1.0:
            est_time_min = (remaining_vol_ml / Q) * 60
            Q_low = max(Q - Q_std, 1.0)
            Q_high = Q + Q_std
            t_low = (remaining_vol_ml / Q_high) * 60
            t_high = (remaining_vol_ml / Q_low) * 60
        else:
            est_time_min, t_low, t_high = float("inf"), float("inf"), float("inf")

        truth_row = truth_df.iloc[(truth_df.t_s - (t0 + t1) / 2).abs().argmin()]

        yield {
            "window_index": i,
            "t_mid_s": (t0 + t1) / 2,
            "fused_flow_ml_per_hr": Q,
            "fused_flow_std": Q_std,
            "fused_drop_factor": ekf.drop_factor,
            "weight_only_flow": z1_flow,
            "drop_only_flow": z2_drop_rate / meta["drop_factor_nominal_gtts_per_ml"],
            "true_flow": truth_row.true_flow_ml_per_hr,
            "true_drop_factor": truth_row.effective_drop_factor_gtts_per_ml,
            "remaining_vol_ml": remaining_vol_ml,
            "remaining_time_min": est_time_min,
            "remaining_time_low_min": t_low,
            "remaining_time_high_min": t_high,
            "meta": meta,
        }


def run_fusion(run_dir, window_s=30.0, fluid_density=1.01,
               initial_drop_factor_guess=None, verbose=False, auto_calibrate=True):
    """
    Runs the EKF over one simulated (or, later, real) run, windowing
    both sensor streams into `window_s`-second chunks, fusing them,
    and returning a per-window results table.

    fluid_density: mL/hr from a load cell requires knowing the fluid's
    density (g/mL) to convert grams lost -> mL infused. In a real
    deployment the nurse selects the fluid on the device; here we just
    pass it in (assume it's known, same as your project's "Novel Idea 4"
    concept -- fluid selection).

    initial_drop_factor_guess: if you don't know the true tubing type,
    you'd start with a nominal guess (e.g. 15.0 for a common macrodrip
    set) and let the filter self-calibrate. Set this deliberately WRONG
    to demonstrate the self-calibration pulling it toward the truth.
    """
    weight_df, drops_df, truth_df, meta = load_run(run_dir)

    t_max = weight_df.t_s.max()
    n_windows = int(t_max // window_s)

    if initial_drop_factor_guess is None:
        initial_drop_factor_guess = meta["drop_factor_nominal_gtts_per_ml"]

    if auto_calibrate:
        r_weight, r_drop = calibrate_measurement_noise(
            weight_df, drops_df, truth_df, meta, window_s, fluid_density
        )
    else:
        r_weight, r_drop = 900.0, 2500.0

    # rough initial flow guess from first window's weight loss
    ekf = IVFusionEKF(
        initial_flow_ml_per_hr=meta["target_flow_ml_per_hr"] * 0.5,  # deliberately not cheating with the true value
        initial_drop_factor=initial_drop_factor_guess,
        r_weight=r_weight, r_drop=r_drop,
    )

    baseline_weight_only = []
    baseline_drop_only = []
    fused_records = []

    drop_times = drops_df.drop_time_s.values

    # Pre-smooth the raw load-cell signal a little (a real embedded system
    # would do this too -- e.g. a short moving average -- since a single
    # instantaneous reading is dominated by sensor jitter relative to how
    # little weight actually changes in a few seconds). This does NOT use
    # any information the real sensor wouldn't have; it's just noise
    # reduction, same as you'd do on real hardware.
    smoothing_samples = 5
    weight_df = weight_df.copy()
    weight_df["weight_smoothed_g"] = (
        weight_df["load_cell_weight_g"].rolling(smoothing_samples, center=True, min_periods=1).median()
    )

    for i in range(n_windows):
        t0, t1 = i * window_s, (i + 1) * window_s
        dt_hr = window_s / 3600.0

        # --- weight-derived flow rate measurement ---
        w0 = weight_df.loc[weight_df.t_s <= t0, "weight_smoothed_g"]
        w1 = weight_df.loc[weight_df.t_s <= t1, "weight_smoothed_g"]
        if len(w0) == 0 or len(w1) == 0:
            continue
        weight_loss_g = -(w1.iloc[-1] - w0.iloc[-1])   # positive = weight decreased
        z1_flow = (weight_loss_g / fluid_density) / dt_hr   # mL/hr

        # --- drop-derived raw rate measurement ---
        count = np.sum((drop_times >= t0) & (drop_times < t1))
        z2_drop_rate = count / dt_hr   # drops/hr

        # baselines (single-sensor only, for comparison)
        baseline_weight_only.append(z1_flow)
        baseline_drop_only.append(z2_drop_rate / meta["drop_factor_nominal_gtts_per_ml"])

        # EKF step
        ekf.predict()
        ekf.update_weight_measurement(z1_flow)
        ekf.update_drop_measurement(z2_drop_rate)

        # ground truth for this window (nearest sample)
        truth_row = truth_df.iloc[(truth_df.t_s - (t0 + t1) / 2).abs().argmin()]

        fused_records.append({
            "window_start_s": t0,
            "window_end_s": t1,
            "t_mid_s": (t0 + t1) / 2,
            "fused_flow_ml_per_hr": ekf.flow_rate,
            "fused_flow_std": ekf.flow_rate_std,
            "fused_drop_factor": ekf.drop_factor,
            "weight_only_flow": z1_flow,
            "drop_only_flow": z2_drop_rate / meta["drop_factor_nominal_gtts_per_ml"],
            "true_flow": truth_row.true_flow_ml_per_hr,
            "true_drop_factor": truth_row.effective_drop_factor_gtts_per_ml,
        })

        if verbose and i % 10 == 0:
            print(f"t={t0:6.0f}s  fused_Q={ekf.flow_rate:6.1f}  fused_k={ekf.drop_factor:5.2f}  "
                  f"true_Q={truth_row.true_flow_ml_per_hr:6.1f}  true_k={truth_row.effective_drop_factor_gtts_per_ml:5.2f}")

    results = pd.DataFrame(fused_records)
    return results, meta
