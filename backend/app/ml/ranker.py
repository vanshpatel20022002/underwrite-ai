"""Comparable ranking model using LightGBM LambdaRank."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.schemas.case import ComparableSale

MODEL_DIR = Path(__file__).parent.parent.parent / "models"


def _comp_features(subject: dict, comp: ComparableSale) -> list[float]:
    return [
        comp.distance_miles,
        comp.similarity_score,
        abs(subject["square_footage"] - comp.square_footage),
        abs(subject["bedrooms"] - comp.bedrooms),
        abs(subject["bathrooms"] - comp.bathrooms),
        abs((subject.get("year_built") or 1990) - (comp.year_built or 1990)),
        comp.sale_price,
        comp.adjusted_price or comp.sale_price,
    ]


def generate_training_data(
    subjects: list[dict], all_comps: list[list[ComparableSale]]
) -> tuple[pd.DataFrame, pd.Series, list[int]]:
    rows = []
    labels = []
    groups = []

    for subject, comps in zip(subjects, all_comps):
        if len(comps) < 2:
            continue
        sorted_comps = sorted(comps, key=lambda c: c.similarity_score, reverse=True)
        group_size = len(sorted_comps)
        groups.append(group_size)
        for rank, comp in enumerate(sorted_comps):
            rows.append(_comp_features(subject, comp))
            labels.append(len(sorted_comps) - rank)

    return pd.DataFrame(rows), pd.Series(labels), groups


def train_ranker(subjects: list[dict], all_comps: list[list[ComparableSale]]) -> dict:
    import lightgbm as lgb

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X, y, groups = generate_training_data(subjects, all_comps)

    if len(groups) < 5:
        return {"status": "skipped", "reason": "insufficient data"}

    train_data = lgb.Dataset(X, label=y, group=groups)
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [5, 10],
        "learning_rate": 0.05,
        "num_leaves": 31,
        "verbose": -1,
    }
    model = lgb.train(params, train_data, num_boost_round=100)
    model.save_model(str(MODEL_DIR / "comp_ranker.txt"))
    return {"status": "trained", "groups": len(groups)}


def rank_comparables(subject: dict, comps: list[ComparableSale]) -> list[ComparableSale]:
    import lightgbm as lgb

    ranker_path = MODEL_DIR / "comp_ranker.txt"
    if not ranker_path.exists() or len(comps) < 2:
        return sorted(comps, key=lambda c: c.similarity_score, reverse=True)

    model = lgb.Booster(model_file=str(ranker_path))
    features = np.array([_comp_features(subject, c) for c in comps])
    scores = model.predict(features)

    ranked = sorted(zip(comps, scores), key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked]


def ndcg_at_k(relevance: list[int], k: int = 5) -> float:
    rel = relevance[:k]
    dcg = sum((2**r - 1) / np.log2(i + 2) for i, r in enumerate(rel))
    ideal = sorted(relevance, reverse=True)[:k]
    idcg = sum((2**r - 1) / np.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0
