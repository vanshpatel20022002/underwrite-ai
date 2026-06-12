from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import get_settings


@lru_cache
def get_reranker() -> CrossEncoder:
    settings = get_settings()
    return CrossEncoder(settings.reranker_model)


def rerank(query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
    if not documents:
        return []

    pairs = [(query, doc["content"]) for doc in documents]
    scores = get_reranker().predict(pairs)

    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return [{**doc, "rerank_score": float(score)} for doc, score in ranked[:top_k]]
