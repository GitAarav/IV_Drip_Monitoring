from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
import sys
import json
import csv

# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATASET_DIR = ROOT_DIR / "synthetic_dataset"

# Allow Python to import kalman_filter_iv.py from root
sys.path.append(str(ROOT_DIR))

from kalman_filter_iv import IVFusionEKF


# ---------------------------------------------------------
# FASTAPI
# ---------------------------------------------------------

app = FastAPI(
    title="IV Drip Monitoring API",
    description="Backend API for the dual-sensor IV monitoring dashboard",
    version="1.0.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "message": "IV Monitoring backend is running"
    }


# ---------------------------------------------------------
# FIND SESSION DIRECTORIES
# ---------------------------------------------------------

def get_session_directories():

    if not DATASET_DIR.exists():
        return []

    return sorted(
        [
            path
            for path in DATASET_DIR.iterdir()
            if path.is_dir() and path.name.startswith("run_")
        ]
    )


# ---------------------------------------------------------
# SESSION LIST
# ---------------------------------------------------------

@app.get("/api/sessions")
def get_sessions():

    sessions = []

    for session_dir in get_session_directories():

        meta_file = session_dir / "meta.json"

        metadata = {}

        if meta_file.exists():

            try:
                with open(meta_file, "r") as f:
                    metadata = json.load(f)

            except Exception:
                metadata = {}

        sessions.append({
            "id": session_dir.name,
            "path": session_dir.name,
            "metadata": metadata
        })

    return sessions


# ---------------------------------------------------------
# FIND CSV FILE
# ---------------------------------------------------------

def find_csv(session_dir, possible_names):

    for name in possible_names:

        file_path = session_dir / name

        if file_path.exists():
            return file_path

    return None


# ---------------------------------------------------------
# READ CSV
# ---------------------------------------------------------

def read_csv_file(file_path):

    if not file_path:
        return []

    rows = []

    with open(file_path, "r", newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:
            rows.append(row)

    return rows


# ---------------------------------------------------------
# SESSION DETAILS
# ---------------------------------------------------------

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):

    session_dir = DATASET_DIR / session_id

    if not session_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    meta_file = session_dir / "meta.json"

    metadata = {}

    if meta_file.exists():

        with open(meta_file, "r") as f:
            metadata = json.load(f)

    weight_file = find_csv(
        session_dir,
        [
            "weight_sensor.csv",
            "weight.csv",
        ]
    )

    drop_file = find_csv(
        session_dir,
        [
            "drop_sensor.csv",
            "drops.csv",
        ]
    )

    ground_truth_file = find_csv(
        session_dir,
        [
            "ground_truth.csv",
        ]
    )

    return {
        "id": session_id,
        "metadata": metadata,
        "weight": read_csv_file(weight_file),
        "drops": read_csv_file(drop_file),
        "ground_truth": read_csv_file(ground_truth_file),
    }


# ---------------------------------------------------------
# ROOT
# ---------------------------------------------------------

@app.get("/")
def root():

    return {
        "message": "IV Drip Monitoring API",
        "docs": "/docs"
    }