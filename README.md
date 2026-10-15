# PRAHAR: Uttarakhand Flash-Flood Intelligence
*Predict · Prepare · Protect*

Multimodal, uncertainty-aware flash-flood warning for Uttarakhand.
- **Inputs:** CWC rain and discharge gauges, USDMA state weather stations, ERA5 reanalysis, IMD flood records, a multi-source 2022–25 event list, GSI landslides and district indices.
- **Models:** calibrated XGBoost plus IMD rainfall thresholds, combined into hybrid warning tiers, with a daily district ranking.
- **Map:** building-level exposure around every rain gauge, on a satellite/terrain map with state-wide place names.

## Quick start
```bash
pip install -r requirements.txt          # pandas, xgboost, scikit-learn, shap, shapely, fastapi, nbclient, pytest, pypdf, openpyxl …
python scripts/run_all.py                 # whole chain: data → labels → train → event CV → calibration → tiers → label audit
                                          # → experiments → external validation → verification → reports → export → impact → tests → audit
python scripts/run_all.py --from export   # only re-export JSON, impact layer, tiles, tests, latency, API check, audit

cd web && npm install && npm run dev      # static mode (reads web/public/data)
```
With the live API:
```bash
python -m uvicorn backend.app:app --port 8000
cd web && npm run dev:api                  # Vite proxies /api → :8000 (mode file web/.env.api)
```
`python scripts/run_notebooks.py` re-executes notebooks 09–14, the step-by-step record of the run.

## Layout
| Path | What |
|---|---|
| `curated_dataset/` | raw curated sources (the pipeline reads the byte-identical copy in `flash-flood-prediction/curated_dataset/`) |
| `data/external/` | downloaded sources: ERA5, USDMA hydromet, DEM tiles, building footprints, OSM, and `labels/` (SANDRP, Sphere India SitReps, EM-DAT, CSE) |
| `src/` | pipeline, features, target, training, event CV, calibration, warning tiers, verification, label audit and experiments, district-day model |
| `backend/` | FastAPI service: data endpoints, `/predict`, `/predict/scenario`, `/health/external` |
| `web/` | React + MapLibre frontend |
| `scripts/` | label building, export, impact layer, tiling, reports, latency benchmark, API checks, end-to-end audit |
| `tests/` | data contracts, label set, online-vs-batch features, API contract |
| `results/` | every metric and report: `label_impact.md`, `model_upgrade.md`, `verification/`, `metrics/`, `labels/` … |

## Data window and labels
- Rainfall runs 2022-02 → 2026-09, discharge 2023-06 → 2025-12, and IMD flood labels end on 2023-08-26.
- Models train on **Window A (2022-02 → 2023-08-25)**. Later hours are replay.
- `scripts/build_labels.py` merges IMD, SANDRP, Sphere India situation reports, EM-DAT and a curated news list into **96 documented events (2022–25)**, each with a source and a date confidence.
  - Events after 2023-08 are an **external validation set**, never training labels, because "no report" doesn't mean "no flood".
  - Plans and decisions are in `LABELS_PLAN.md` and `MODEL_UPGRADE_PLAN.md`.

## Headline results (test month Aug 2023, after the label-join fix)
- **XGBoost:** ROC-AUC 0.71, PR-AUC 0.15 (base rate 5.8 %), F1 0.32. Before the district-name fix these were 0.53 / 0.04 / 0.08.
- **Hybrid tiers at ≥ ALERT:** precision 0.23, recall 0.65. District-day CSI is 0.17 against IMD labels and 0.20 against the fuller event list.
- **External validation:** 7 of 21 documented post-2023 events were caught where a gauge was reporting.
- **Experiments tested and not adopted** (ensemble, event-fitted rain thresholds, district-day alerts, label v2): each was judged by a rule fixed before it ran.
  - The limit is the labels and the gauges' blindness to local cloudbursts, not the model class. See `results/model_upgrade.md`.

## Verifying a run
- `python scripts/audit_pipeline.py` checks that every stage exists, is newer than its inputs and agrees with the previous stage.
- `pytest -q tests` checks data contracts, the label set, feature equivalence and the API.

## What this is not
A decision-support prototype. It gives estimates of hazard and exposure with stated uncertainty, not damage, casualty or evacuation decisions.

## Track B: Space mode (Mapping Flood Damage from Space)
Satellite-only damage mapping for **any area and date**. It uses only the inputs Track B allows: Sentinel-1/2, Copernicus DEM GLO-30, pre-event OSM via ohsome, and Kuro Siwo for training. Full write-up: `TRACKB_REPORT.md`.
```bash
pip install rasterio onnxruntime networkx scipy requests pandas shapely matplotlib
# put the trained model in models/space/ (floodseg.onnx + floodseg_meta.json); train it with notebooks/trackB_train_floodseg_colab.ipynb
python -m src.space.run    --name dharali --bbox 78.70,30.98,78.90,31.10 --date "2025-08-05 08:15"   # UTC
python -m src.space.report --name dharali     # one-page sitrep: results/space/dharali/sitrep.md / .html
python scripts/export_space.py --name dharali # dashboard data: web/public/data/space_dharali.json + space_index.json
# Trishuli GLOF case study, checked against Copernicus EMS EMSR927 (vectors used ONLY for checking):
python -m src.space.run --name trishuli --bbox 85.30,28.14,85.40,28.29 --date "2026-08-25 22:00"
python scripts/check_emsr.py --name trishuli --emsr data/external/emsr927 --aois 1,2
```
Live runs from the dashboard: start the API (`uvicorn backend.app:app`) and set `VITE_API_URL`. The Space page's "Map any flood" box then calls `POST /space/run` and polls `GET /space/jobs/{id}`.

What each run adds on top of the flood map:
- Sentinel-2 fusion where the sky is clear (MNDWI new water; vegetated → barren debris);
- rescue priorities (buildings per cut-off settlement);
- helicopter landing candidates (ICAO Annex 14 slope limits);
- a flood-path tracer (D8 on the Copernicus DEM);
- Hindi and Nepali sitrep summaries;
- run timing.
Outputs in `results/space/<name>/`:
- flood map (AI and rule baseline GeoTIFFs);
- hit buildings, roads and bridges (GeoJSON);
- cut-off settlements (`cutoff.json`);
- `summary.json`, `map.png`, and the sitrep.

Attribution: Contains modified Copernicus Sentinel data 2025–2026 · Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the EU and ESA; all rights reserved · © OpenStreetMap contributors · Kuro Siwo (Bountos et al., NeurIPS 2024, CC BY 4.0).
