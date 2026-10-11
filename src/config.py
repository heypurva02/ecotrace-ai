"""Project paths and configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_default_db = DATA_DIR / "ecotrace.db"
DB_PATH = Path(os.environ.get("ECOTRACE_DB_PATH") or _default_db)

METHODOLOGY_VERSION = "1.0.0"
APP_NAME = "EcoTrace AI"
APP_FULL_TITLE = (
    "An AI-Assisted Life Cycle Assessment and Sustainability "
    "Optimisation Platform for Industrial Products"
)
COURSE_CODE = "CSL225"
INSTITUTION = "The NorthCap University, Gurugram, Haryana, India"

FACTOR_CSV = DATA_DIR / "emission_factors.csv"
DEMO_PRODUCTS_CSV = DATA_DIR / "demo_products.csv"
DEMO_ACTIVITIES_CSV = DATA_DIR / "demo_activities.csv"
TEMPLATE_CSV = DATA_DIR / "assessment_template.csv"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xlsx"}

ACTIVITY_CATEGORIES = [
    "Raw materials",
    "Electricity",
    "Fuel and direct energy use",
    "Manufacturing processes",
    "Inbound transport",
    "Outbound transport",
    "Water consumption",
    "Waste treatment",
]

LIFE_CYCLE_STAGES = [
    "Raw material supply",
    "Inbound logistics",
    "Manufacturing",
    "Outbound logistics",
]

MATERIAL_TYPES = ["Aluminium", "Steel", "Other"]

BOUNDARIES = {
    "cradle_to_gate": {
        "label": "Cradle-to-gate",
        "stages": list(LIFE_CYCLE_STAGES),
        "explanation": (
            "Includes the activity data entered for raw-material supply, inbound "
            "logistics, manufacturing, and outbound logistics. Product use and "
            "end-of-life are outside this prototype boundary. Only processes with "
            "entered activity data are calculated."
        ),
    },
    "gate_to_gate": {
        "label": "Gate-to-gate",
        "stages": ["Manufacturing"],
        "explanation": (
            "Includes only manufacturing-stage activity data. Upstream materials, "
            "transport, use, and end-of-life are excluded unless the user later "
            "widens the boundary and supplies data."
        ),
    },
    "selected": {
        "label": "Selected production and transport stages",
        "stages": None,
        "explanation": (
            "Includes only the life-cycle stages the user selects. Unselected "
            "stages are excluded from the numerical total even if activity rows exist."
        ),
    },
}

DATA_ORIGINS = ["primary", "secondary", "estimated", "demonstration"]
PROVENANCE_TYPES = ["verified", "illustrative", "user_supplied"]
