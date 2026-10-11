"""Load and expose the environmental factor registry."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from src.config import FACTOR_CSV
from src.database import Database
from src.models import EmissionFactor


REQUIRED_COLUMNS = [
    "factor_id",
    "name",
    "activity_category",
    "material_or_activity_type",
    "factor_value",
    "factor_unit",
    "reference_activity_unit",
    "geographic_scope",
    "reference_year",
    "technology_description",
    "source_organisation",
    "source_title",
    "source_url",
    "data_classification",
    "source_publication",
    "licence_note",
    "uncertainty_note",
    "provenance",
    "date_added",
]


def load_factors_from_csv(path: Optional[Path] = None) -> list[EmissionFactor]:
    csv_path = path or FACTOR_CSV
    if not csv_path.exists():
        return []
    factors: list[EmissionFactor] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Factor CSV is missing columns: {', '.join(missing)}")
        for row in reader:
            if not (row.get("factor_id") or "").strip():
                continue
            payload = {
                "factor_id": row["factor_id"].strip(),
                "name": row["name"].strip(),
                "activity_category": row["activity_category"].strip(),
                "material_or_activity_type": row["material_or_activity_type"].strip(),
                "factor_value": float(row["factor_value"]),
                "factor_unit": row["factor_unit"].strip() or "kg CO2e",
                "reference_activity_unit": row["reference_activity_unit"].strip(),
                "geographic_scope": row.get("geographic_scope") or "",
                "reference_year": row.get("reference_year") or "",
                "technology_description": row.get("technology_description") or "",
                "source_organisation": row.get("source_organisation") or "",
                "source_title": row.get("source_title") or "",
                "source_url": row.get("source_url") or "",
                "data_classification": row.get("data_classification") or "",
                "source_publication": row.get("source_publication") or "",
                "licence_note": row.get("licence_note") or "",
                "uncertainty_note": row.get("uncertainty_note") or "",
                "provenance": row["provenance"].strip(),
            }
            if (row.get("date_added") or "").strip():
                payload["date_added"] = row["date_added"].strip()
            factors.append(EmissionFactor(**payload))
    return factors


def seed_registry(db: Database, path: Optional[Path] = None) -> int:
    factors = load_factors_from_csv(path)
    for factor in factors:
        db.upsert_factor(factor, overwrite_illustrative=True)
    return len(factors)
