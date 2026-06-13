# MLOps — Experiment Tracking and Drift Detection

Two lightweight, local-first tools for treating this as an evaluated ML system rather than a static demo:

1. **MLflow** — tracks every training run (params, metrics, artifacts)
2. **Evidently** — data drift and quality report on the property sales dataset

Both tools are optional extras — the main workflow does not depend on them.

---

## MLflow Experiment Tracking

MLflow is integrated into the LightGBM training path (`backend/app/ml/train.py`). Each call to `train_price_model()` automatically logs:

| Category | What is logged |
|---|---|
| **Params** | `model_type`, `learning_rate`, `num_leaves`, `feature_fraction`, `num_boost_round`, `test_split`, `feature_cols`, `dataset_size`, `data_source` |
| **Metrics** | `mae`, `rmse`, `mape`, `train_size` |
| **Artifacts** | `price_model.txt`, `residual_stats.json`, `metrics.json` |

Tracking is **silently skipped** if MLflow is not installed — it never blocks a training run.

### Setup and usage

```bash
# Install
pip install mlflow

# Train (MLflow run is created automatically)
docker compose -f docker/docker-compose.yml exec api python scripts/seed_data.py

# View the MLflow UI
mlflow ui --backend-store-uri backend/mlruns
# Open: http://localhost:5000
```

MLflow writes run data to `backend/mlruns/` by default (relative to where the training script runs inside the container). The directory is gitignored.

### What the UI shows

- **Experiment**: `underwriting-price-model`
- One **run** per training execution with all params, metrics, and the model artifact
- Compare runs after retraining with new data to track MAE/RMSE regression over time

---

## Evidently Data Drift Report

`mlops/evidently_drift.py` generates an HTML drift and data quality report for the property sales dataset.

Columns analyzed:
- `sale_price` (target)
- `square_footage`
- `lot_size`
- `year_built`
- `property_type`

### Setup and usage

```bash
# Install
pip install evidently

# Run with the seeded training data (splits 80/20 for demo if only one file exists)
python mlops/evidently_drift.py

# Run with a separate newer dataset
python mlops/evidently_drift.py \
    --reference data/property_sales.csv \
    --current   data/property_sales_new.csv

# Custom output path
python mlops/evidently_drift.py --output reports/my_report.html
```

Output: `reports/evidently_drift_report.html` — open in any browser.

### When to run this

- After downloading a new Calgary assessment CSV to check for distribution shift
- Before retraining to understand whether the new data differs meaningfully from the training data
- As a scheduled quality gate in a staging pipeline

### Note on the demo split

When only `property_sales.csv` is available, the script splits it 80/20 (reference vs current) to demonstrate the workflow. The report will show low drift because both halves come from the same file — this is expected and clearly noted in the output.

---

## Limitations

- MLflow tracking is local-only (`backend/mlruns/`). For team use, configure a remote tracking server via `MLFLOW_TRACKING_URI`.
- The Evidently report is a static HTML file — it does not auto-update.
- Neither tool is wired into CI by default. Add them as optional steps if needed.
- These tools add no runtime dependency to the FastAPI application.
