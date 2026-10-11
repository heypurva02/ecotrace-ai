"""SQLite persistence with foreign keys and parameterised queries."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from src.config import DB_PATH, METHODOLOGY_VERSION
from src.models import (
    ActivityInput,
    AssessmentInput,
    CalculationResult,
    EmissionFactor,
    ProductInput,
    utc_now_iso,
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    material_type TEXT NOT NULL,
    notes TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    production_quantity REAL NOT NULL,
    production_quantity_unit TEXT NOT NULL,
    functional_unit TEXT NOT NULL,
    functional_unit_quantity REAL NOT NULL,
    reporting_period TEXT NOT NULL,
    location TEXT NOT NULL,
    boundary TEXT NOT NULL,
    selected_stages_json TEXT,
    notes TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    data_origin TEXT,
    created_at TEXT NOT NULL,
    demo_key TEXT
);

CREATE TABLE IF NOT EXISTS emission_factors (
    factor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    activity_category TEXT NOT NULL,
    material_or_activity_type TEXT NOT NULL,
    factor_value REAL NOT NULL,
    factor_unit TEXT NOT NULL,
    reference_activity_unit TEXT NOT NULL,
    geographic_scope TEXT,
    reference_year TEXT,
    technology_description TEXT,
    source_organisation TEXT,
    source_title TEXT,
    source_url TEXT,
    data_classification TEXT,
    source_publication TEXT,
    licence_note TEXT,
    uncertainty_note TEXT,
    provenance TEXT NOT NULL,
    date_added TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    life_cycle_stage TEXT NOT NULL,
    quantity REAL NOT NULL,
    quantity_unit TEXT NOT NULL,
    factor_id TEXT,
    supplier_note TEXT,
    data_origin TEXT,
    evidence_reference TEXT,
    include_in_total INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    run_type TEXT NOT NULL,
    total_kg_co2e REAL NOT NULL,
    total_tonnes_co2e REAL NOT NULL,
    footprint_per_fu REAL,
    functional_unit TEXT,
    included_count INTEGER,
    excluded_count INTEGER,
    missing_factor_count INTEGER,
    warnings_json TEXT,
    data_quality_json TEXT,
    input_fingerprint TEXT,
    methodology_version TEXT,
    by_stage_json TEXT,
    by_category_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculation_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES calculation_runs(id) ON DELETE CASCADE,
    activity_id INTEGER,
    category TEXT,
    description TEXT,
    life_cycle_stage TEXT,
    quantity REAL,
    quantity_unit TEXT,
    converted_quantity REAL,
    converted_unit TEXT,
    factor_id TEXT,
    factor_value REAL,
    factor_unit TEXT,
    source_reference TEXT,
    conversion_applied TEXT,
    contribution_kg_co2e REAL,
    included INTEGER,
    percentage REAL,
    factor_snapshot_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    modifications_json TEXT NOT NULL,
    baseline_run_id INTEGER REFERENCES calculation_runs(id) ON DELETE SET NULL,
    scenario_run_id INTEGER REFERENCES calculation_runs(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    category TEXT,
    description TEXT,
    contribution_kg_co2e REAL,
    included INTEGER,
    percentage REAL,
    factor_id TEXT
);

CREATE TABLE IF NOT EXISTS evidence_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER REFERENCES activity_records(id) ON DELETE CASCADE,
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
    reference_text TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    file_hash TEXT,
    imported_at TEXT NOT NULL,
    row_count INTEGER,
    valid_count INTEGER,
    error_count INTEGER,
    warning_count INTEGER,
    summary TEXT,
    assessment_id INTEGER
);
"""


class Database:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialise()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialise(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_factor(self, factor: EmissionFactor, overwrite_illustrative: bool = True) -> None:
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT provenance FROM emission_factors WHERE factor_id = ?",
                (factor.factor_id,),
            ).fetchone()
            if existing and existing["provenance"] == "user_supplied" and not overwrite_illustrative:
                return
            conn.execute(
                """
                INSERT INTO emission_factors (
                    factor_id, name, activity_category, material_or_activity_type,
                    factor_value, factor_unit, reference_activity_unit, geographic_scope,
                    reference_year, technology_description, source_organisation, source_title,
                    source_url, data_classification, source_publication, licence_note,
                    uncertainty_note, provenance, date_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(factor_id) DO UPDATE SET
                    name=excluded.name,
                    activity_category=excluded.activity_category,
                    material_or_activity_type=excluded.material_or_activity_type,
                    factor_value=excluded.factor_value,
                    factor_unit=excluded.factor_unit,
                    reference_activity_unit=excluded.reference_activity_unit,
                    geographic_scope=excluded.geographic_scope,
                    reference_year=excluded.reference_year,
                    technology_description=excluded.technology_description,
                    source_organisation=excluded.source_organisation,
                    source_title=excluded.source_title,
                    source_url=excluded.source_url,
                    data_classification=excluded.data_classification,
                    source_publication=excluded.source_publication,
                    licence_note=excluded.licence_note,
                    uncertainty_note=excluded.uncertainty_note,
                    provenance=excluded.provenance
                WHERE emission_factors.provenance != 'user_supplied'
                """,
                (
                    factor.factor_id,
                    factor.name,
                    factor.activity_category,
                    factor.material_or_activity_type,
                    factor.factor_value,
                    factor.factor_unit,
                    factor.reference_activity_unit,
                    factor.geographic_scope,
                    factor.reference_year,
                    factor.technology_description,
                    factor.source_organisation,
                    factor.source_title,
                    factor.source_url,
                    factor.data_classification,
                    factor.source_publication,
                    factor.licence_note,
                    factor.uncertainty_note,
                    factor.provenance,
                    factor.date_added,
                ),
            )

    def list_factors(self) -> list[EmissionFactor]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM emission_factors ORDER BY factor_id").fetchall()
        return [EmissionFactor.model_validate(dict(r)) for r in rows]

    def get_factor(self, factor_id: str) -> Optional[EmissionFactor]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM emission_factors WHERE factor_id = ?", (factor_id,)
            ).fetchone()
        return EmissionFactor.model_validate(dict(row)) if row else None

    def factor_map(self) -> dict[str, EmissionFactor]:
        return {f.factor_id: f for f in self.list_factors()}

    def create_product(self, product: ProductInput) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO products (name, category, material_type, notes, is_demo, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product.name,
                    product.category,
                    product.material_type,
                    product.notes,
                    int(product.is_demo),
                    utc_now_iso(),
                ),
            )
            return int(cur.lastrowid)

    def create_assessment(self, product_id: int, assessment: AssessmentInput, demo_key: Optional[str] = None) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO assessments (
                    product_id, name, production_quantity, production_quantity_unit,
                    functional_unit, functional_unit_quantity, reporting_period, location,
                    boundary, selected_stages_json, notes, is_demo, data_origin, created_at, demo_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    assessment.name,
                    assessment.production_quantity,
                    assessment.production_quantity_unit,
                    assessment.functional_unit,
                    assessment.functional_unit_quantity,
                    assessment.reporting_period,
                    assessment.location,
                    assessment.boundary,
                    json.dumps(assessment.selected_stages),
                    assessment.notes,
                    int(assessment.is_demo),
                    assessment.data_origin,
                    utc_now_iso(),
                    demo_key,
                ),
            )
            return int(cur.lastrowid)

    def find_demo_assessment(self, demo_key: str) -> Optional[int]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM assessments WHERE demo_key = ?", (demo_key,)
            ).fetchone()
        return int(row["id"]) if row else None

    def replace_activities(self, assessment_id: int, activities: list[ActivityInput]) -> list[int]:
        ids: list[int] = []
        with self.connect() as conn:
            conn.execute("DELETE FROM activity_records WHERE assessment_id = ?", (assessment_id,))
            for activity in activities:
                cur = conn.execute(
                    """
                    INSERT INTO activity_records (
                        assessment_id, category, description, life_cycle_stage, quantity,
                        quantity_unit, factor_id, supplier_note, data_origin, evidence_reference,
                        include_in_total, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment_id,
                        activity.category,
                        activity.description,
                        activity.life_cycle_stage,
                        activity.quantity,
                        activity.quantity_unit,
                        activity.factor_id,
                        activity.supplier_note,
                        activity.data_origin,
                        activity.evidence_reference,
                        int(activity.include_in_total),
                        utc_now_iso(),
                    ),
                )
                ids.append(int(cur.lastrowid))
                if activity.evidence_reference:
                    conn.execute(
                        """
                        INSERT INTO evidence_references (activity_id, assessment_id, reference_text, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (cur.lastrowid, assessment_id, activity.evidence_reference, utc_now_iso()),
                    )
        return ids

    def add_activities(self, assessment_id: int, activities: list[ActivityInput]) -> list[int]:
        ids: list[int] = []
        with self.connect() as conn:
            for activity in activities:
                cur = conn.execute(
                    """
                    INSERT INTO activity_records (
                        assessment_id, category, description, life_cycle_stage, quantity,
                        quantity_unit, factor_id, supplier_note, data_origin, evidence_reference,
                        include_in_total, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment_id,
                        activity.category,
                        activity.description,
                        activity.life_cycle_stage,
                        activity.quantity,
                        activity.quantity_unit,
                        activity.factor_id,
                        activity.supplier_note,
                        activity.data_origin,
                        activity.evidence_reference,
                        int(activity.include_in_total),
                        utc_now_iso(),
                    ),
                )
                ids.append(int(cur.lastrowid))
        return ids

    def get_activities(self, assessment_id: int) -> list[ActivityInput]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activity_records WHERE assessment_id = ? ORDER BY id",
                (assessment_id,),
            ).fetchall()
        return [
            ActivityInput(
                activity_id=r["id"],
                category=r["category"],
                description=r["description"],
                life_cycle_stage=r["life_cycle_stage"],
                quantity=r["quantity"],
                quantity_unit=r["quantity_unit"],
                factor_id=r["factor_id"],
                supplier_note=r["supplier_note"] or "",
                data_origin=r["data_origin"] or "secondary",
                evidence_reference=r["evidence_reference"] or "",
                include_in_total=bool(r["include_in_total"]),
            )
            for r in rows
        ]

    def get_assessment(self, assessment_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT a.*, p.name AS product_name, p.category AS product_category,
                       p.material_type, p.notes AS product_notes, p.is_demo AS product_is_demo
                FROM assessments a
                JOIN products p ON p.id = a.product_id
                WHERE a.id = ?
                """,
                (assessment_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_assessments(self, search: str = "") -> list[dict[str, Any]]:
        query = """
            SELECT a.*, p.name AS product_name, p.material_type,
                   (
                     SELECT total_kg_co2e FROM calculation_runs
                     WHERE assessment_id = a.id AND run_type = 'baseline'
                     ORDER BY id DESC LIMIT 1
                   ) AS latest_total_kg,
                   (
                     SELECT created_at FROM calculation_runs
                     WHERE assessment_id = a.id AND run_type = 'baseline'
                     ORDER BY id DESC LIMIT 1
                   ) AS latest_calc_at,
                   (
                     SELECT json_extract(data_quality_json, '$.rating') FROM calculation_runs
                     WHERE assessment_id = a.id AND run_type = 'baseline'
                     ORDER BY id DESC LIMIT 1
                   ) AS data_quality_status
            FROM assessments a
            JOIN products p ON p.id = a.product_id
        """
        params: tuple = ()
        if search.strip():
            query += " WHERE a.name LIKE ? OR p.name LIKE ? OR p.material_type LIKE ?"
            like = f"%{search.strip()}%"
            params = (like, like, like)
        query += " ORDER BY a.id DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def save_calculation_run(
        self,
        assessment_id: int,
        result: CalculationResult,
        run_type: str = "baseline",
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO calculation_runs (
                    assessment_id, run_type, total_kg_co2e, total_tonnes_co2e, footprint_per_fu,
                    functional_unit, included_count, excluded_count, missing_factor_count,
                    warnings_json, data_quality_json, input_fingerprint, methodology_version,
                    by_stage_json, by_category_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    run_type,
                    result.total_kg_co2e,
                    result.total_tonnes_co2e,
                    result.footprint_per_functional_unit,
                    result.functional_unit,
                    result.included_activity_count,
                    result.excluded_activity_count,
                    result.missing_factor_count,
                    json.dumps(result.warnings),
                    json.dumps(result.data_quality),
                    result.input_fingerprint,
                    result.methodology_version or METHODOLOGY_VERSION,
                    json.dumps(result.by_stage),
                    json.dumps(result.by_category),
                    result.calculated_at,
                ),
            )
            run_id = int(cur.lastrowid)
            for item in result.contributions:
                conn.execute(
                    """
                    INSERT INTO calculation_contributions (
                        run_id, activity_id, category, description, life_cycle_stage, quantity,
                        quantity_unit, converted_quantity, converted_unit, factor_id, factor_value,
                        factor_unit, source_reference, conversion_applied, contribution_kg_co2e,
                        included, percentage, factor_snapshot_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        item.activity_id,
                        item.category,
                        item.description,
                        item.life_cycle_stage,
                        item.quantity,
                        item.quantity_unit,
                        item.converted_quantity,
                        item.converted_unit,
                        item.factor_id,
                        item.factor_value,
                        item.factor_unit,
                        item.source_reference,
                        item.conversion_applied,
                        item.contribution_kg_co2e,
                        int(item.included),
                        item.percentage,
                        json.dumps(item.factor_snapshot),
                        result.calculated_at,
                    ),
                )
        result.calculation_run_id = run_id
        return run_id

    def get_latest_run(self, assessment_id: int, run_type: str = "baseline") -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM calculation_runs
                WHERE assessment_id = ? AND run_type = ?
                ORDER BY id DESC LIMIT 1
                """,
                (assessment_id, run_type),
            ).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM calculation_runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            contribs = conn.execute(
                "SELECT * FROM calculation_contributions WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        data = dict(row)
        data["contributions"] = [dict(c) for c in contribs]
        return data

    def list_runs(self, assessment_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM calculation_runs
                WHERE assessment_id = ?
                ORDER BY id DESC
                """,
                (assessment_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_scenario(
        self,
        assessment_id: int,
        name: str,
        description: str,
        modifications: dict[str, Any],
        baseline_run_id: int,
        scenario_run_id: int,
        scenario_contributions: list[dict[str, Any]],
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO scenarios (
                    assessment_id, name, description, modifications_json,
                    baseline_run_id, scenario_run_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    name,
                    description,
                    json.dumps(modifications),
                    baseline_run_id,
                    scenario_run_id,
                    utc_now_iso(),
                ),
            )
            scenario_id = int(cur.lastrowid)
            for item in scenario_contributions:
                conn.execute(
                    """
                    INSERT INTO scenario_contributions (
                        scenario_id, category, description, contribution_kg_co2e,
                        included, percentage, factor_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scenario_id,
                        item.get("category"),
                        item.get("description"),
                        item.get("contribution_kg_co2e"),
                        int(bool(item.get("included"))),
                        item.get("percentage"),
                        item.get("factor_id"),
                    ),
                )
        return scenario_id

    def list_scenarios(self, assessment_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scenarios WHERE assessment_id = ? ORDER BY id DESC",
                (assessment_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_saved_scenario(self, assessment_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM scenarios WHERE assessment_id = ? ORDER BY id DESC LIMIT 1",
                (assessment_id,),
            ).fetchone()
        return dict(row) if row else None

    def log_import(self, **kwargs: Any) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO import_logs (
                    filename, file_hash, imported_at, row_count, valid_count,
                    error_count, warning_count, summary, assessment_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kwargs.get("filename"),
                    kwargs.get("file_hash"),
                    utc_now_iso(),
                    kwargs.get("row_count", 0),
                    kwargs.get("valid_count", 0),
                    kwargs.get("error_count", 0),
                    kwargs.get("warning_count", 0),
                    kwargs.get("summary"),
                    kwargs.get("assessment_id"),
                ),
            )
            return int(cur.lastrowid)

    def find_import_hash(self, file_hash: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM import_logs WHERE file_hash = ? ORDER BY id DESC LIMIT 1",
                (file_hash,),
            ).fetchone()
        return dict(row) if row else None

    def delete_assessment(self, assessment_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))

    def dashboard_metrics(self) -> dict[str, Any]:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM assessments").fetchone()["n"]
            products = conn.execute("SELECT COUNT(DISTINCT product_id) AS n FROM assessments").fetchone()["n"]
            latest = conn.execute(
                """
                SELECT a.id, a.name, p.name AS product_name, r.total_kg_co2e, r.footprint_per_fu,
                       r.functional_unit, r.data_quality_json, r.created_at
                FROM calculation_runs r
                JOIN assessments a ON a.id = r.assessment_id
                JOIN products p ON p.id = a.product_id
                WHERE r.run_type = 'baseline'
                ORDER BY r.id DESC LIMIT 1
                """
            ).fetchone()
            low_quality = conn.execute(
                """
                SELECT COUNT(*) AS n FROM (
                    SELECT assessment_id, json_extract(data_quality_json, '$.overall_score') AS score
                    FROM calculation_runs
                    WHERE run_type = 'baseline'
                    GROUP BY assessment_id
                    HAVING score IS NOT NULL AND score < 60
                )
                """
            ).fetchone()["n"]
            incomplete = conn.execute(
                """
                SELECT COUNT(*) AS n FROM (
                    SELECT assessment_id FROM calculation_runs
                    WHERE run_type = 'baseline' AND missing_factor_count > 0
                    GROUP BY assessment_id
                )
                """
            ).fetchone()["n"]
            recent = conn.execute(
                """
                SELECT a.id, a.created_at, p.name AS product_name, r.total_kg_co2e
                FROM assessments a
                JOIN products p ON p.id = a.product_id
                LEFT JOIN calculation_runs r ON r.id = (
                    SELECT id FROM calculation_runs
                    WHERE assessment_id = a.id AND run_type = 'baseline'
                    ORDER BY id DESC LIMIT 1
                )
                ORDER BY a.id DESC LIMIT 12
                """
            ).fetchall()
            comparable = conn.execute(
                """
                SELECT r.footprint_per_fu, r.functional_unit
                FROM calculation_runs r
                WHERE r.run_type = 'baseline' AND r.footprint_per_fu IS NOT NULL
                """
            ).fetchall()
            scenario_row = conn.execute(
                """
                SELECT s.assessment_id, br.total_kg_co2e AS baseline_kg, sr.total_kg_co2e AS scenario_kg
                FROM scenarios s
                JOIN calculation_runs br ON br.id = s.baseline_run_id
                JOIN calculation_runs sr ON sr.id = s.scenario_run_id
                ORDER BY s.id DESC LIMIT 1
                """
            ).fetchone()
        footprints = [r["footprint_per_fu"] for r in comparable]
        units = {r["functional_unit"] for r in comparable}
        avg_fu = None
        if footprints and len(units) == 1:
            avg_fu = sum(footprints) / len(footprints)
        potential = None
        if scenario_row and scenario_row["baseline_kg"]:
            potential = scenario_row["baseline_kg"] - scenario_row["scenario_kg"]
        return {
            "total_assessments": total,
            "distinct_products": products,
            "latest": dict(latest) if latest else None,
            "low_quality_or_incomplete": (low_quality or 0) + (incomplete or 0),
            "recent": [dict(r) for r in recent],
            "average_footprint_per_fu": avg_fu,
            "average_fu_label": next(iter(units)) if len(units) == 1 else None,
            "potential_reduction_kg": potential,
        }


_DB: Optional[Database] = None


def get_db(path: Optional[Path] = None) -> Database:
    global _DB
    if path is not None:
        return Database(path)
    if _DB is None:
        _DB = Database()
    return _DB
