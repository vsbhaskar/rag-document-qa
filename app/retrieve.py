from app import config
from app.store import collection, model


def retrieve(question: str, user_id: int | None = None,
             k: int = config.TOP_K, min_score: float = config.MIN_SCORE):
    """user_id=None searches everything. Only the eval script does that; the API always passes a user."""
    if collection.count() == 0:
        return []
    where = {"user_id": user_id} if user_id is not None else None
    q_emb = model.encode([question], normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=q_emb, n_results=k, where=where)
    scored = [
        (doc, meta, 1 - dist / 2)
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]
    return [item for item in scored if item[2] >= min_score]