from pathlib import Path
import sys
import json

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

DATASET_DIR = ROOT_DIR / "synthetic_dataset"

# Allow Python to import the existing research code
sys.path.insert(0, str(ROOT_DIR))


# ============================================================
# EXISTING EKF
# ============================================================

from kalman_filter_iv import stream_fusion


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="IV Drip Monitoring API",
    description="Backend API for the Dual-Sensor Predictive IV Monitoring System",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_run_directory(session_id: str) -> Path:
    """
    Return the directory for a requested synthetic run.
    """

    run_dir = DATASET_DIR / session_id

    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found",
        )

    return run_dir


def load_metadata(session_id: str):
    """
    Load meta.json for a session.
    """

    run_dir = get_run_directory(session_id)

    meta_file = run_dir / "meta.json"

    if not meta_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"meta.json not found for '{session_id}'",
        )

    with open(meta_file, "r") as f:
        return json.load(f)


def clean_value(value):
    """
    Convert NumPy/Pandas values into JSON-safe values.
    """

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if pd.isna(value):
        return None

    return value


def clean_record(record):
    """
    Convert a dictionary into JSON-safe values.
    """

    return {
        key: clean_value(value)
        for key, value in record.items()
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "IV Drip Monitoring API",
        "docs": "/docs",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "dataset_exists": DATASET_DIR.exists(),
        "dataset_path": str(DATASET_DIR),
    }


# ============================================================
# LIST SESSIONS
# ============================================================

@app.get("/api/sessions")
def get_sessions():
    """
    Return all synthetic validation sessions.
    """

    if not DATASET_DIR.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Dataset directory not found: {DATASET_DIR}",
        )

    sessions = []

    for run_dir in sorted(DATASET_DIR.glob("run_*")):

        if not run_dir.is_dir():
            continue

        meta_file = run_dir / "meta.json"

        if not meta_file.exists():
            continue

        try:
            with open(meta_file, "r") as f:
                meta = json.load(f)

            sessions.append({
                "id": run_dir.name,

                "target_flow_ml_per_hr": meta.get(
                    "target_flow_ml_per_hr"
                ),

                "drop_factor_name": meta.get(
                    "drop_factor_name"
                ),

                "drop_factor_nominal_gtts_per_ml": meta.get(
                    "drop_factor_nominal_gtts_per_ml"
                ),

                "fluid_name": meta.get(
                    "fluid_name"
                ),

                "bag_volume_ml": meta.get(
                    "bag_volume_ml"
                ),

                "duration_s": meta.get(
                    "duration_s"
                ),

                "anomaly": meta.get(
                    "anomaly",
                    "none"
                ),

                "anomaly_start_frac": meta.get(
                    "anomaly_start_frac"
                ),
            })

        except Exception as exc:
            print(
                f"Could not read metadata for {run_dir.name}: {exc}"
            )

    return sessions


# ============================================================
# SESSION DETAILS
# ============================================================

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):

    run_dir = get_run_directory(session_id)

    meta = load_metadata(session_id)

    result = {
        "id": session_id,
        "metadata": meta,
    }

    # --------------------------------------------------------
    # Weight sensor information
    # --------------------------------------------------------

    weight_file = run_dir / "weight_sensor.csv"

    if weight_file.exists():

        weight_df = pd.read_csv(weight_file)

        result["weight_sensor"] = {
            "rows": len(weight_df),
            "columns": list(weight_df.columns),
        }

        # Return a reduced set for the frontend.
        #
        # We don't send tens of thousands of rows unnecessarily.
        if len(weight_df) > 1000:
            sample = weight_df.iloc[
                :: max(1, len(weight_df) // 1000)
            ]
        else:
            sample = weight_df

        result["weight_data"] = [
            clean_record(row)
            for row in sample.to_dict(
                orient="records"
            )
        ]

    else:
        result["weight_sensor"] = {
            "rows": 0,
            "columns": [],
        }

        result["weight_data"] = []


    # --------------------------------------------------------
    # Drop sensor information
    # --------------------------------------------------------

    drop_file = run_dir / "drop_sensor.csv"

    if drop_file.exists():

        drop_df = pd.read_csv(drop_file)

        result["drop_sensor"] = {
            "rows": len(drop_df),
            "columns": list(drop_df.columns),
        }

    else:

        result["drop_sensor"] = {
            "rows": 0,
            "columns": [],
        }


    # --------------------------------------------------------
    # Ground truth information
    #
    # This is VALIDATION ONLY.
    # --------------------------------------------------------

    truth_file = run_dir / "ground_truth.csv"

    if truth_file.exists():

        truth_df = pd.read_csv(truth_file)

        result["ground_truth"] = {
            "rows": len(truth_df),
            "columns": list(truth_df.columns),
        }

    else:

        result["ground_truth"] = {
            "rows": 0,
            "columns": [],
        }


    return result


# ============================================================
# RUN EKF FUSION
# ============================================================

@app.get("/api/sessions/{session_id}/fusion")
def get_fusion(session_id: str):

    run_dir = get_run_directory(session_id)

    try:

        print(
            f"Running EKF fusion for {session_id}..."
        )

        results = []

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # This calls YOUR existing research implementation.
        #
        # We are not recreating the EKF in JavaScript.
        # ----------------------------------------------------

        for row in stream_fusion(
            str(run_dir),
            window_s=60.0,
            fluid_density=1.01,
            auto_calibrate=True,
        ):

            results.append(
                clean_record(row)
            )

        print(
            f"EKF completed: {len(results)} windows"
        )

        return {
            "session_id": session_id,
            "window_s": 60.0,
            "count": len(results),
            "rows": results,
        }

    except Exception as exc:

        print(
            f"EKF ERROR for {session_id}:"
        )

        print(exc)

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )