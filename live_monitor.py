"""
LIVE MONITOR -- looks and behaves like an actual bedside device screen.
===========================================================================
Unlike live_demo.py (which scrolls a log line per reading, plus a graph),
this redraws ONE screen in place, over and over, the way a real IV
monitor's display would: you don't see a history log on a real device,
you see the current status, updating.

Each "tick" represents one new batch of sensor data arriving (60 real
seconds of simulated IV time, by default) and getting processed by the
filter. The screen is cleared and redrawn fresh each time, so it feels
like watching one continuously-updating readout, not a printout.

HOW TO RUN:
    python live_monitor.py
    (Ctrl+C to stop early)

PACE CONTROL:
    TICK_DELAY_S near the top controls how long each screen stays up
    before the next reading comes in and refreshes it. Default is 1.0
    second per tick -- slow enough to actually read comfortably during
    a demo. Raise it (e.g. 2.0) to slow it down further, lower it to
    speed through faster.
"""

import os
import sys
import time
from kalman_filter_iv import stream_fusion

# ----------------------------------------------------------------------
WINDOW_S = 60.0        # how much simulated IV time each reading batch covers
FLUID_DENSITY = 1.01
TICK_DELAY_S = 1.0     # real seconds to pause between each screen update

# Pre-picked demo scenarios -- run the script and just type 1, 2, or 3.
# No file editing needed to switch what you're demoing.
SCENARIOS = {
    "1": ("synthetic_dataset/run_005",      "Normal session -- runs cleanly start to finish"),
    "2": ("synthetic_dataset/run_012",  "Occlusion partway through -- watch Status change"),
    "3": ("synthetic_dataset/run_016",       "Leak / disconnect partway through -- watch Status change"),
}
# ----------------------------------------------------------------------


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def format_time(minutes):
    if minutes == float("inf"):
        return "N/A (flow ~0)"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m"


def status_label(step):
    """Simple, honest status flag based on how far the fused flow has
    drifted from the session's prescribed target rate, plus a completion
    check once the bag is effectively empty."""
    if step["remaining_vol_ml"] <= 2.0:
        return "*** INFUSION COMPLETE -- BAG EMPTY, REPLACE ***"
    Q = step["fused_flow_ml_per_hr"]
    target = step["meta"]["target_flow_ml_per_hr"]
    pct_dev = abs(Q - target) / target * 100 if target > 0 else 0
    if pct_dev > 40:
        return "*** CHECK LINE -- FLOW DEVIATES FROM PRESCRIBED RATE ***"
    elif pct_dev > 15:
        return "Monitoring -- minor deviation from prescribed rate"
    else:
        return "Normal"


def draw_screen(step, elapsed_ticks, total_ticks):
    t_min = step["t_mid_s"] / 60
    Q = step["fused_flow_ml_per_hr"]
    k = step["fused_drop_factor"]
    rem = step["remaining_time_min"]
    rem_lo = step["remaining_time_low_min"]
    rem_hi = step["remaining_time_high_min"]
    rem_vol = step["remaining_vol_ml"]
    meta = step["meta"]

    clear_screen()
    print("=" * 52)
    print("        IV INFUSION MONITOR -- LIVE")
    print("=" * 52)
    print(f" Patient session:      {meta['run_id']}")
    print(f" Fluid / tubing:       {meta['fluid_name']}, {meta['drop_factor_name']}")
    print(f" Elapsed time:         {t_min:6.1f} min")
    print("-" * 52)
    print(f" Current flow rate:    {Q:6.1f} mL/hr")
    print(f" Drop factor (live):   {k:6.2f} gtts/mL   (self-calibrating)")
    print(f" Estimated fluid left: {rem_vol:6.1f} mL")
    print("-" * 52)
    print(f" TIME REMAINING:       {format_time(rem)}")
    print(f"   confidence range:   {format_time(rem_lo)}  -  {format_time(rem_hi)}")
    print("-" * 52)
    print(f" Status:               {status_label(step)}")
    print("=" * 52)
    print(f" reading {elapsed_ticks}/{total_ticks}   "
          f"(updates every {WINDOW_S:.0f}s of infusion time)")
    print(" Ctrl+C to stop")


def main():
    print("=" * 52)
    print("   IV INFUSION MONITOR -- choose a demo scenario")
    print("=" * 52)
    for key, (path, desc) in SCENARIOS.items():
        print(f"  {key}) {desc}")
    choice = input("\nType 1, 2, or 3 and press Enter: ").strip()
    run_dir, desc = SCENARIOS.get(choice, SCENARIOS["1"])

    print(f"\nConnecting to session: {run_dir} ...")
    time.sleep(1)

    steps = list(stream_fusion(run_dir, window_s=WINDOW_S, fluid_density=FLUID_DENSITY))
    total = len(steps)

    try:
        for i, step in enumerate(steps, start=1):
            draw_screen(step, i, total)
            time.sleep(TICK_DELAY_S)
            if step["remaining_vol_ml"] <= 2.0:
                print("\nBag empty -- ending session monitoring.")
                break
    except KeyboardInterrupt:
        pass

    print("\nSession monitoring ended.")


if __name__ == "__main__":
    main()
