"""
Vector store service for RAG-based context retrieval.

Uses Pinecone for serverless vector storage and OpenAI embeddings.
Each chat gets its own namespace for vector isolation.

Keys are user-provided (stored encrypted in DB), not env vars.
All public functions accept pinecone_key and openai_key as explicit params.
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
INDEX_NAME = "chatmerge"

# Per-key client caches (avoids recreating connections on every call)
_pinecone_index_cache: Dict[str, Any] = {}
_openai_client_cache: Dict[str, AsyncOpenAI] = {}
# Track which Pinecone keys have had their index verified
_index_verified: set = set()


def _get_pinecone_index(pinecone_key: str):
    if pinecone_key not in _pinecone_index_cache:
        pc = Pinecone(api_key=pinecone_key)
        _pinecone_index_cache[pinecone_key] = pc.Index(INDEX_NAME)
    return _pinecone_index_cache[pinecone_key]


def _get_openai_client(openai_key: str) -> AsyncOpenAI:
    if openai_key not in _openai_client_cache:
        _openai_client_cache[openai_key] = AsyncOpenAI(api_key=openai_key)
    return _openai_client_cache[openai_key]


async def ensure_index_exists(pinecone_key: str):
    """Create the Pinecone index if it doesn't exist yet. Called lazily on first use."""
    if pinecone_key in _index_verified:
        return
    try:
        pc = Pinecone(api_key=pinecone_key)
        existing = [idx.name for idx in pc.list_indexes()]
        if INDEX_NAME not in existing:
            logger.info(f"Creating Pinecone index: {INDEX_NAME}")
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            logger.info(f"Pinecone index {INDEX_NAME} created")
        else:
            logger.info(f"Pinecone index {INDEX_NAME} already exists")
        _index_verified.add(pinecone_key)
    except Exception as e:
        logger.error(f"Failed to ensure Pinecone index exists: {e}")
        raise


async def embed_text(text: str, openai_key: str) -> List[float]:
    client = _get_openai_client(openai_key)
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


async def store_message_vector(
    chat_id: str,
    message_id: str,
    content: str,
    role: str,
    pinecone_key: str,
    openai_key: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
):
    """Store a message embedding in the chat's Pinecone namespace."""
    if not pinecone_key or not openai_key:
        return
    try:
        await ensure_index_exists(pinecone_key)

        text_to_embed = content
        if attachments:
            for att in attachments:
                text_to_embed += f"\n\n[Attachment: {att.get('file_name', 'unknown')}]"

        embedding = await embed_text(text_to_embed, openai_key)
        index = _get_pinecone_index(pinecone_key)
        index.upsert(
            vectors=[{
                "id": message_id,
                "values": embedding,
                "metadata": {
                    "chat_id": chat_id,
                    "role": role,
                    "content": content[:1000],
                    "has_attachments": bool(attachments),
                },
            }],
            namespace=chat_id,
        )
        logger.info(f"Stored vector for message {message_id} in namespace {chat_id}")
    except Exception as e:
        logger.error(f"Failed to store message vector: {e}")


async def query_relevant_context(
    chat_id: str,
    query_text: str,
    pinecone_key: str,
    openai_key: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Query the vector store for messages relevant to query_text."""
    if not pinecone_key or not openai_key:
        return []
    try:
        await ensure_index_exists(pinecone_key)
        query_embedding = await embed_text(query_text, openai_key)
        index = _get_pinecone_index(pinecone_key)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=chat_id,
            include_metadata=True,
        )
        context_items = [
            {"message_id": m.id, "score": m.score, "metadata": m.metadata}
            for m in results.matches
        ]
        logger.info(f"Retrieved {len(context_items)} context items for chat {chat_id}")
        return context_items
    except Exception as e:
        logger.error(f"Failed to query vector store: {e}")
        return []


async def merge_vector_namespaces(
    source_chat_ids: List[str],
    target_chat_id: str,
    pinecone_key: str,
    openai_key: str,
) -> bool:
    """
    Copy all vectors from source namespaces into the merged chat's namespace.

    Uses index.list() to enumerate IDs and index.fetch() to retrieve vectors —
    the correct approach for Pinecone serverless. A dummy zero-vector query does
    NOT reliably enumerate all vectors and must not be used.

    Returns True if at least one vector was successfully copied.
    """
    if not pinecone_key:
        logger.warning("merge_vector_namespaces: no Pinecone key provided")
        return False

    try:
        await ensure_index_exists(pinecone_key)
        index = _get_pinecone_index(pinecone_key)
        total_copied = 0
        FETCH_BATCH = 200
        UPSERT_BATCH = 100

        for source_id in source_chat_ids:
            try:
                # Enumerate all vector IDs via the list API (serverless only)
                all_ids: List[str] = []
                for id_batch in index.list(namespace=source_id):
                    if isinstance(id_batch, list):
                        all_ids.extend(id_batch)
                    else:
                        all_ids.append(id_batch)

                if not all_ids:
                    logger.info(f"No vectors in namespace {source_id}, skipping")
                    continue

                logger.info(f"Found {len(all_ids)} vectors in namespace {source_id}")

                # Fetch actual vectors (with values) in batches
                vectors_to_upsert = []
                for i in range(0, len(all_ids), FETCH_BATCH):
                    batch_ids = all_ids[i:i + FETCH_BATCH]
                    fetch_result = index.fetch(ids=batch_ids, namespace=source_id)
                    for original_id, vec in fetch_result.vectors.items():
                        metadata = dict(vec.metadata or {})
                        metadata["source_chat_id"] = source_id
                        metadata["original_chat_id"] = metadata.get("chat_id", source_id)
                        metadata["chat_id"] = target_chat_id
                        vectors_to_upsert.append({
                            "id": f"{source_id}_{original_id}",
                            "values": vec.values,
                            "metadata": metadata,
                        })

                # Upsert into target namespace
                for i in range(0, len(vectors_to_upsert), UPSERT_BATCH):
                    batch = vectors_to_upsert[i:i + UPSERT_BATCH]
                    index.upsert(vectors=batch, namespace=target_chat_id)
                    total_copied += len(batch)

                logger.info(f"Copied {len(vectors_to_upsert)} vectors from {source_id} → {target_chat_id}")

            except Exception as e:
                logger.error(f"Failed to copy vectors from namespace {source_id}: {e}")
                continue

        logger.info(f"Namespace merge complete: {total_copied} total vectors in {target_chat_id}")
        return total_copied > 0

    except Exception as e:
        logger.error(f"Failed to merge vector namespaces: {e}")
        return False


async def fuse_namespaces(
    source_chat_ids: List[str],
    target_chat_id: str,
    pinecone_key: str,
    threshold: float = 0.82,
) -> Dict[str, int]:
    """
    Intelligently fuse vector namespaces from multiple source chats.

    Algorithm:
      - Initialize working set with all vectors from first source
      - For each subsequent source vector:
          - Compute cosine similarity with every vector in working set (locally, via numpy)
          - If best similarity >= threshold: fuse (average embeddings, merge metadata)
          - Else: add as unique vector (keep both)
      - Upsert entire working set into target namespace

    Result size: anywhere from max(|A|,|B|) to |A|+|B|, depending on overlap.
    Threshold 0.82 targets ~middle of that range.

    Returns {"fused": int, "kept": int, "total": int} on success.
    Raises on failure — caller should fall back to merge_vector_namespaces.
    """
    if not pinecone_key:
        raise ValueError("Pinecone key is required for fuse_namespaces")

    await ensure_index_exists(pinecone_key)
    index = _get_pinecone_index(pinecone_key)

    FETCH_BATCH = 200
    UPSERT_BATCH = 100

    def _fetch_all_vectors(source_id: str) -> List[Dict]:
        """Fetch all vectors from a namespace."""
        all_ids: List[str] = []
        for id_batch in index.list(namespace=source_id):
            if isinstance(id_batch, list):
                all_ids.extend(id_batch)
            else:
                all_ids.append(id_batch)
        if not all_ids:
            return []
        vectors = []
        for i in range(0, len(all_ids), FETCH_BATCH):
            batch_ids = all_ids[i:i + FETCH_BATCH]
            fetch_result = index.fetch(ids=batch_ids, namespace=source_id)
            for vid, vec in fetch_result.vectors.items():
                vectors.append({
                    "id": vid,
                    "values": vec.values,
                    "metadata": dict(vec.metadata or {}),
                })
        return vectors

    # Fetch vectors from all source namespaces
    source_vectors: List[Tuple[str, List[Dict]]] = []
    for source_id in source_chat_ids:
        vecs = _fetch_all_vectors(source_id)
        logger.info(f"fuse_namespaces: fetched {len(vecs)} vectors from namespace {source_id}")
        source_vectors.append((source_id, vecs))

    if all(len(v) == 0 for _, v in source_vectors):
        logger.warning("fuse_namespaces: all source namespaces empty, nothing to fuse")
        return {"fused": 0, "kept": 0, "total": 0}

    # Initialize working set from first non-empty source
    working_set: List[Dict] = []
    first_source_id = source_chat_ids[0]
    for source_id, vecs in source_vectors:
        if vecs:
            first_source_id = source_id
            for vec in vecs:
                working_set.append({
                    "id": f"{source_id}_{vec['id']}",
                    "values": np.array(vec["values"], dtype=np.float32),
                    "metadata": {
                        **vec["metadata"],
                        "type": "kept",
                        "source_chat_id": source_id,
                        "chat_id": target_chat_id,
                    },
                })
            break

    logger.info(f"fuse_namespaces: initialized working set with {len(working_set)} vectors from {first_source_id}")

    fused_count = 0
    kept_count = 0

    # Skip the first source (already in working set), fuse remaining into it
    first_processed = False
    for source_id, vecs in source_vectors:
        if not first_processed:
            first_processed = True
            continue  # skip first source — already in working set
        if not vecs:
            continue

        # Build numpy matrix for current working set
        working_values = np.stack([w["values"] for w in working_set])  # (N, D)
        working_norms = np.linalg.norm(working_values, axis=1, keepdims=False) + 1e-8  # (N,)

        for vec in vecs:
            query = np.array(vec["values"], dtype=np.float32)
            query_norm = float(np.linalg.norm(query)) + 1e-8

            # Cosine similarity with all working set vectors in one matmul
            sims = working_values @ query / (working_norms * query_norm)  # (N,)
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])

            if best_sim >= threshold:
                # Fuse: average embeddings, merge metadata
                nn = working_set[best_idx]
                avg_values = (nn["values"] + query) / 2.0
                norm = float(np.linalg.norm(avg_values)) + 1e-8
                avg_values = avg_values / norm  # normalize

                nn_content = nn["metadata"].get("content", "")
                vec_content = vec["metadata"].get("content", "")

                working_set[best_idx] = {
                    "id": nn["id"],
                    "values": avg_values,
                    "metadata": {
                        "type": "fused",
                        "content": f"[A]: {nn_content}\n[B]: {vec_content}",
                        "source_a_chat_id": first_source_id,
                        "source_b_chat_id": source_id,
                        "chat_id": target_chat_id,
                    },
                }
                # Keep numpy matrix in sync
                working_values[best_idx] = avg_values
                working_norms[best_idx] = float(np.linalg.norm(avg_values)) + 1e-8
                fused_count += 1
            else:
                # Unique: add to working set
                working_set.append({
                    "id": f"{source_id}_{vec['id']}",
                    "values": query,
                    "metadata": {
                        **vec["metadata"],
                        "type": "kept",
                        "source_chat_id": source_id,
                        "chat_id": target_chat_id,
                    },
                })
                working_values = np.vstack([working_values, query.reshape(1, -1)])
                working_norms = np.append(working_norms, float(np.linalg.norm(query)) + 1e-8)
                kept_count += 1

    logger.info(
        f"fuse_namespaces: {fused_count} pairs fused, {kept_count} unique kept, "
        f"{len(working_set)} total vectors → {target_chat_id}"
    )

    # Upsert working set into target namespace
    upsert_vectors = [
        {"id": w["id"], "values": w["values"].tolist(), "metadata": w["metadata"]}
        for w in working_set
    ]
    for i in range(0, len(upsert_vectors), UPSERT_BATCH):
        index.upsert(vectors=upsert_vectors[i:i + UPSERT_BATCH], namespace=target_chat_id)

    logger.info(f"fuse_namespaces: upserted {len(upsert_vectors)} vectors into {target_chat_id}")
    return {"fused": fused_count, "kept": kept_count, "total": len(upsert_vectors)}


async def delete_namespace(chat_id: str, pinecone_key: str):
    """Delete all vectors in a namespace when a chat is deleted."""
    if not pinecone_key:
        return
    try:
        index = _get_pinecone_index(pinecone_key)
        index.delete(delete_all=True, namespace=chat_id)
        logger.info(f"Deleted namespace {chat_id}")
    except Exception as e:
        logger.error(f"Failed to delete namespace {chat_id}: {e}")


async def get_namespace_stats(chat_id: str, pinecone_key: str) -> Dict[str, Any]:
    """Get vector count for a chat namespace."""
    if not pinecone_key:
        return {"vector_count": 0}
    try:
        index = _get_pinecone_index(pinecone_key)
        stats = index.describe_index_stats()
        ns = stats.namespaces.get(chat_id, {})
        return {"vector_count": getattr(ns, "vector_count", 0)}
    except Exception as e:
        logger.error(f"Failed to get namespace stats: {e}")
        return {"vector_count": 0}
