# EcoTrace AI

**An AI-Assisted Life Cycle Assessment and Sustainability Optimisation Platform for Industrial Products**

CSL225 minor project · The NorthCap University, Gurugram, Haryana, India  
Python / Streamlit screening prototype for aluminium and steel manufacturing examples.

This application helps a user enter industrial activity data, map those data to a documented emission-factor registry, calculate a screening greenhouse-gas footprint with ordinary Python arithmetic, inspect hotspots, model supported what-if scenarios, generate rule-based recommendations, and export PDF/CSV/Excel reports. Results persist in a local SQLite database.

**Academic disclaimer.** EcoTrace AI is a teaching and screening prototype. It is not ISO-certified, not independently verified, not an Environmental Product Declaration, and not an EU CBAM (or other regulatory) filing. Illustrative emission factors are labelled as such and are not official Indian government factors. A low numerical result does not mean a product is environmentally friendly.

## Features

- Multi-page Streamlit interface with a persistent sidebar
- Validated new-assessment workflow and CSV/XLSX import
- Deterministic calculation engine (no language model in the arithmetic)
- Factor registry with provenance metadata and per-run snapshots
- Data-quality heuristic (internal prototype indicator, not a certification)
- Scenario optimiser that copies inputs and recalculates
- Local rule-based sustainability advisor; optional LLM rephrasing off by default
- Assessment history in SQLite (survives restart)
- PDF (ReportLab), CSV, and Excel exports from the selected assessment
- Methodology page and labelled demonstration dataset

## Screens and navigation

The Streamlit home page is the **Dashboard**. Additional pages:

1. New Assessment  
2. Assessment History  
3. Environmental Analysis  
4. Scenario Optimiser  
5. AI Sustainability Advisor  
6. Reports & Exports  
7. Methodology & Data Sources  
8. About the Project  

## Technology stack

Python 3.11+ (developed against the system Python 3.x), Streamlit, Pandas, NumPy, Plotly, Pydantic, sqlite3, openpyxl, ReportLab, pytest.

## Folder structure

```
ecotrace-ai/
├── app.py                 # Dashboard / application entry
├── pages/                 # Multipage navigation
├── src/                   # Calculation, database, reports (no Streamlit in calculations.py)
├── data/                  # Factor CSV, templates, SQLite database after first run
├── tests/
├── reports/               # Generated PDFs/workbooks
├── assets/
├── requirements.txt
└── README.md
```

## Setup (macOS)

```bash
cd ~/Projects/ecotrace-ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

Then open the URL printed in the terminal (usually http://localhost:8501).

## Setup (Windows)

```bat
cd %USERPROFILE%\Projects\ecotrace-ai
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

## Demo data

On the Dashboard, click **Load demonstration dataset**.

- Creates a synthetic aluminium can-body assessment and a steel bracket assessment if they are not already present.
- Does not duplicate those demo keys on a second click.
- Does not overwrite user-created assessments.
- Demo activity quantities are invented teaching data.
- All bundled factors are **illustrative**.
- The aluminium demo includes one unmapped chemicals row and a saved hypothetical scenario (electricity −20%, alternative electricity factor, transport −30%, recycled share 60%).

## New assessment walkthrough

1. Open **New Assessment**.
2. Enter product name, material (Aluminium / Steel / Other), production quantity, functional unit, location, and reporting period.
3. Choose the system boundary and read the plain-language summary.
4. Add activity rows (category, quantity, unit, factor ID).
5. Review the calculation preview (mapped rows, missing factors, warnings).
6. Click **Run deterministic calculation and save**.
7. Open **Environmental Analysis** for charts and hotspots.
8. Open **Scenario Optimiser**, move sliders, then save a scenario only if you want it stored.
9. Open **Reports & Exports** to download PDF and CSV files.

## Imports

Download the blank template from New Assessment → CSV / Excel import. Required columns:

`product_name, activity_name, activity_category, life_cycle_stage, quantity, quantity_unit, factor_id, source_note, data_origin, reporting_period`

Optional: `supplier`, `assessment_name`, `material_type`, `functional_unit`, `location`.  
Invalid rows are listed in an error report and are not imported. Re-uploading the same file contents produces a duplicate warning.

## Reports

Reports always use the **currently selected** saved assessment (sidebar). PDF files are also written under `reports/`.

## Database location

Default file: `data/ecotrace.db` (relative to the project directory, not the current working directory).

Override:

```bash
export ECOTRACE_DB_PATH=/absolute/path/to/ecotrace.db
```

To back up assessments, copy that SQLite file while the app is idle.

## Calculation formula

For each included activity:

`activity_emissions_kg_co2e = converted_quantity × emission_factor`

`total_kg_co2e = sum(included activity emissions)`

`footprint_per_functional_unit = total_kg_co2e / functional_unit_quantity` (only when the denominator is positive)

Identical inputs, factor snapshots, boundary, and methodology version produce the same fingerprint. Editing a factor later does not rewrite historical snapshots.

## Optional LLM

Copy `.env.example` to `.env`. Leave `ECOTRACE_LLM_ENABLED=false` unless you intentionally provide `ECOTRACE_LLM_API_KEY`. The model may only rephrase calculated summaries. If the API is missing, times out, or fails, the local advisor continues to work.

## Tests

```bash
python -m pytest -q
```

## Troubleshooting

| Issue | What to try |
|---|---|
| `streamlit: command not found` | Activate `.venv` and reinstall requirements. |
| Blank dashboard | Load the demonstration dataset or create an assessment. |
| Import rejected | Check required columns, numeric quantities, and factor IDs against the methodology table. |
| Incompatible units | Convert to the factor reference family (for example Wh → kWh, g → kg) or pick another factor. |
| PDF button error | Calculate a baseline first. |
| Port in use | `streamlit run app.py --server.port 8502` |

## Known limitations

- Factor values in the bundled registry are **illustrative demonstration values**, not verified national inventory or EPD factors.
- Only GHG (kg CO₂e) is calculated. Water has a GHG factor; it is not a water-scarcity indicator.
- Use and end-of-life stages are outside the default model unless the user adds data.
- Recycled-content sliders only rebalance paired primary/recycled aluminium or steel rows already in the assessment.
- Data-quality scores are an internal weighted heuristic.
- Single-user local app; no authentication.
- Optional LLM is unused unless explicitly enabled.

## Sources and factor provenance

See **Methodology & Data Sources** in the app and `data/emission_factors.csv`. Where a source URL or official publication could not be verified for this prototype, the row is classified as `illustrative` and must not be cited as an official factor.

## Future improvements

Replace illustrative factors with documented applicable sources; add further impact categories; support supplier EPDs; quantify uncertainty; independent methodological review if a verified study is required.
