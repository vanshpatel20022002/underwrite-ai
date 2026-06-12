import uuid

from qdrant_client import QdrantClient, models as qmodels
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import get_settings
from app.retrieval.embeddings import embed_texts

COLLECTION_NAME = "underwriting_docs"
VECTOR_SIZE = 384


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection() -> None:
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


async def index_chunks(case_id: str, chunks: list[dict]) -> int:
    ensure_collection()
    client = get_qdrant_client()

    texts = [c["content"] for c in chunks]
    vectors = embed_texts(texts)

    points = []
    for chunk, vector in zip(chunks, vectors):
        point_id = str(uuid.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "case_id": case_id,
                    "doc_type": chunk["doc_type"],
                    "page": chunk.get("page"),
                    "section": chunk.get("section"),
                    "content": chunk["content"],
                    "source_file": chunk["source_file"],
                },
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


def hybrid_search(
    case_id: str,
    query: str,
    doc_types: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    ensure_collection()
    client = get_qdrant_client()
    query_vector = embed_texts([query])[0]

    conditions = [qmodels.FieldCondition(key="case_id", match=qmodels.MatchValue(value=case_id))]
    if doc_types:
        conditions.append(
            qmodels.FieldCondition(key="doc_type", match=qmodels.MatchAny(any=doc_types))
        )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=qmodels.Filter(must=conditions),
        limit=limit,
    ).points

    return [
        {
            "score": hit.score,
            "doc_type": hit.payload.get("doc_type"),
            "page": hit.payload.get("page"),
            "section": hit.payload.get("section"),
            "content": hit.payload.get("content"),
            "source_file": hit.payload.get("source_file"),
        }
        for hit in results
    ]
