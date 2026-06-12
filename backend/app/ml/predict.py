import json
from pathlib import Path

from app.ml.features import FEATURE_COLS, subject_to_features
from app.schemas.case import ConfidenceInterval, ShapFeature

MODEL_DIR = Path(__file__).parent.parent.parent / "models"


def _load_model():
    import lightgbm as lgb

    model_path = MODEL_DIR / "price_model.txt"
    if not model_path.exists():
        raise FileNotFoundError("Price model not trained. Run scripts/seed_data.py first.")
    return lgb.Booster(model_file=str(model_path))


def _load_residual_stats() -> dict:
    stats_path = MODEL_DIR / "residual_stats.json"
    if stats_path.exists():
        return json.loads(stats_path.read_text())
    return {"p10": -50000, "p90": 50000, "std": 75000}


def predict_value(subject: dict) -> dict:
    import numpy as np
    import shap

    model = _load_model()
    X = subject_to_features(subject)
    estimate = float(model.predict(X)[0])

    stats = _load_residual_stats()
    ci = ConfidenceInterval(
        low=estimate + stats["p10"],
        high=estimate + stats["p90"],
        level=0.8,
    )

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]

    shap_features = [
        ShapFeature(feature=FEATURE_COLS[i], contribution=float(shap_values[0][i]))
        for i in np.argsort(np.abs(shap_values[0]))[::-1][:5]
    ]

    confidence = max(0.0, min(1.0, 1.0 - stats["std"] / max(estimate, 1) * 0.5))

    return {
        "estimated_value": round(estimate, 2),
        "confidence_interval": ci,
        "confidence_score": round(confidence, 3),
        "shap_features": shap_features,
    }
