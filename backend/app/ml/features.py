from datetime import date

import numpy as np
import pandas as pd

PROPERTY_TYPE_MAP = {
    "single_family": 0,
    "condo": 1,
    "townhouse": 2,
    "multi_family": 3,
}


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    features = df.copy()
    features["age"] = date.today().year - features["year_built"].fillna(1980)
    features["property_type_code"] = features["property_type"].map(PROPERTY_TYPE_MAP).fillna(0)
    features["lot_size"] = features["lot_size"].fillna(features["lot_size"].median())
    if "sale_date" in features.columns:
        features["sale_recency_days"] = (
            pd.Timestamp.now() - pd.to_datetime(features["sale_date"])
        ).dt.days
    else:
        features["sale_recency_days"] = 180
    return features


FEATURE_COLS = [
    "latitude",
    "longitude",
    "square_footage",
    "bedrooms",
    "bathrooms",
    "age",
    "lot_size",
    "property_type_code",
    "sale_recency_days",
]


def subject_to_features(subject: dict) -> np.ndarray:
    age = date.today().year - (subject.get("year_built") or 1980)
    return np.array(
        [
            [
                subject.get("latitude", 0.0),
                subject.get("longitude", 0.0),
                subject["square_footage"],
                subject["bedrooms"],
                subject["bathrooms"],
                age,
                subject.get("lot_size") or 5000,
                PROPERTY_TYPE_MAP.get(subject.get("property_type", "single_family"), 0),
                30,
            ]
        ]
    )
