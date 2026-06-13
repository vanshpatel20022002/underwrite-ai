"""Train LightGBM pricing model on property sales data."""

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

from app.config import get_settings
from app.ml.features import FEATURE_COLS, build_feature_frame

try:
    import mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False

settings = get_settings()
MODEL_DIR = Path(__file__).parent.parent.parent / "models"


def train_price_model(data_path: str | None = None) -> dict:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if data_path is None:
        data_path = str(Path(settings.data_dir) / "property_sales.csv")

    df = pd.read_csv(data_path)
    features = build_feature_frame(df)
    X = features[FEATURE_COLS]
    y = features["sale_price"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    train_data = lgb.Dataset(X_train, label=y_train)
    params = {
        "objective": "regression",
        "metric": "mae",
        "learning_rate": 0.05,
        "num_leaves": 63,
        "feature_fraction": 0.8,
        "verbose": -1,
    }
    model = lgb.train(params, train_data, num_boost_round=300)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mape = float(np.mean(np.abs((y_test - preds) / y_test)) * 100)

    model_path = MODEL_DIR / "price_model.txt"
    model.save_model(str(model_path))

    residuals = y_test - preds
    residual_stats = {
        "p10": float(np.percentile(residuals, 10)),
        "p90": float(np.percentile(residuals, 90)),
        "std": float(np.std(residuals)),
    }
    stats_path = MODEL_DIR / "residual_stats.json"
    stats_path.write_text(json.dumps(residual_stats))

    metrics = {"mae": mae, "rmse": rmse, "mape": mape, "train_size": len(X_train)}
    metrics_path = MODEL_DIR / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))

    _log_mlflow(params, metrics, model_path, stats_path, metrics_path, data_path, X)

    return metrics


def _log_mlflow(
    lgb_params: dict,
    metrics: dict,
    model_path: Path,
    stats_path: Path,
    metrics_path: Path,
    data_path: str,
    X: "pd.DataFrame",
) -> None:
    if not _MLFLOW_AVAILABLE:
        return
    try:
        mlflow.set_experiment("underwriting-price-model")
        with mlflow.start_run():
            mlflow.log_params({
                "model_type": "lightgbm",
                "objective": lgb_params["objective"],
                "learning_rate": lgb_params["learning_rate"],
                "num_leaves": lgb_params["num_leaves"],
                "feature_fraction": lgb_params["feature_fraction"],
                "num_boost_round": 300,
                "test_split": 0.2,
                "random_state": 42,
                "feature_cols": ",".join(X.columns.tolist()),
                "dataset_size": len(X),
                "data_source": Path(data_path).name,
            })
            mlflow.log_metrics({
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "mape": metrics["mape"],
                "train_size": float(metrics["train_size"]),
            })
            for artifact in (model_path, stats_path, metrics_path):
                if artifact.exists():
                    mlflow.log_artifact(str(artifact))
    except Exception as exc:
        # MLflow tracking is non-critical — never block a training run
        print(f"[mlflow] tracking skipped: {exc}")
