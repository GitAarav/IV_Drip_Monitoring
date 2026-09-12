"""
LIVE DEMO -- readings arrive one at a time, remaining time updates live.
===========================================================================
THIS is the file that answers "show him it's a live system, not a
pre-computed dump." It processes the session ONE 60-second window at a
time (same as a real device would receive one new load-cell reading and
one new batch of drop-sensor counts every so often), and after EACH new
window arrives, it reprints the current best estimate of remaining time.

It is NOT a fake replay: the filter genuinely only knows about data up
through the current window when it prints its estimate -- it has not
looked ahead. That's what makes this an honest "live" demo rather than
a pre-computed animation.

HOW TO RUN:
    python live_demo.py
    (Ctrl+C to stop early if you don't want to wait for the full run)

WHAT YOU'LL SEE:
  - A live-updating terminal line, once per window, showing the current
    fused flow rate and the current remaining-time estimate + range.
  - A live-updating plot window (if your system supports a GUI display)
    showing the flow-rate estimate building up over time and a large
    "time remaining" readout that changes as new data arrives.

SPEED CONTROL:
  A real 3-hour IV session obviously can't be demoed in real time.
  PLAYBACK_DELAY_S controls how long to pause between each new window
  so you can actually see it update -- lower = faster demo. At the
  default of 0.15s per window (60 real seconds of IV time per window),
  a ~3 hour session finishes in well under a minute.
"""

import time
import sys
import numpy as np
import matplotlib.pyplot as plt
from kalman_filter_iv import stream_fusion

# ----------------------------------------------------------------------
RUN_DIR = "synthetic_dataset/run_005_none"   # change this to demo a different session
WINDOW_S = 60.0
FLUID_DENSITY = 1.01
PLAYBACK_DELAY_S = 0.15    # pause (seconds) between each new reading window
SHOW_LIVE_PLOT = True      # set False if you only want the terminal feed
# ----------------------------------------------------------------------


def format_time(minutes):
    if minutes == float("inf"):
        return "n/a (flow ~0)"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m"


def main():
    print(f"Starting LIVE monitoring of: {RUN_DIR}")
    print(f"(Each printed line = one new batch of sensor readings arriving)\n")
    time.sleep(1)

    ts, flows, trues, remain_times, remain_lo, remain_hi = [], [], [], [], [], []

    if SHOW_LIVE_PLOT:
        plt.ion()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
        line_fused, = ax1.plot([], [], label="Fused flow estimate", linewidth=2)
        line_true, = ax1.plot([], [], "k--", label="True flow (hidden from filter)", linewidth=1)
        ax1.set_xlabel("minutes elapsed"); ax1.set_ylabel("mL/hr")
        ax1.set_title("Live flow rate estimate")
        ax1.legend()

        ax2.axis("off")
        big_text = ax2.text(0.5, 0.6, "", ha="center", va="center", fontsize=28, family="monospace")
        sub_text = ax2.text(0.5, 0.35, "", ha="center", va="center", fontsize=13, family="monospace", color="gray")
        ax2.set_title("Current remaining-time estimate")

    try:
        for step in stream_fusion(RUN_DIR, window_s=WINDOW_S, fluid_density=FLUID_DENSITY):
            t_min = step["t_mid_s"] / 60
            Q = step["fused_flow_ml_per_hr"]
            rem = step["remaining_time_min"]
            rem_lo = step["remaining_time_low_min"]
            rem_hi = step["remaining_time_high_min"]

            print(f"[t={t_min:6.1f} min]  new reading in  ->  "
                  f"flow={Q:6.1f} mL/hr   remaining ≈ {format_time(rem):>9}  "
                  f"(range: {format_time(rem_lo)} - {format_time(rem_hi)})")
            sys.stdout.flush()

            ts.append(t_min); flows.append(Q); trues.append(step["true_flow"])
            remain_times.append(rem)

            if SHOW_LIVE_PLOT:
                line_fused.set_data(ts, flows)
                line_true.set_data(ts, trues)
                ax1.relim(); ax1.autoscale_view()

                big_text.set_text(format_time(rem))
                sub_text.set_text(f"range: {format_time(rem_lo)} - {format_time(rem_hi)}\n"
                                   f"(t = {t_min:.1f} min elapsed, flow = {Q:.1f} mL/hr)")
                fig.canvas.draw()
                fig.canvas.flush_events()

            time.sleep(PLAYBACK_DELAY_S)

    except KeyboardInterrupt:
        print("\n(stopped early)")

    print("\nLive session finished.")
    if SHOW_LIVE_PLOT:
        plt.ioff()
        plt.savefig("live_demo_final_state.png", dpi=110)
        print("Saved final view to live_demo_final_state.png")
        plt.show()


if __name__ == "__main__":
    main()
