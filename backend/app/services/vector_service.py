"""
Vector store service for RAG-based context retrieval.

Uses Pinecone for serverless vector storage and OpenAI embeddings.
Each chat gets its own namespace for vector isolation.
"""

import logging
import os
from typing import List, Dict, Optional, Any
from uuid import uuid4
from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

# Embedding model configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536

# Pinecone index name
INDEX_NAME = "chatmerge"

# Singleton Pinecone client
_pinecone_client = None
_openai_client = None


def is_configured() -> bool:
    """Check if Pinecone is configured"""
    return bool(os.getenv("PINECONE_API_KEY"))


def get_pinecone_client() -> Pinecone:
    """Get or create Pinecone client singleton"""
    global _pinecone_client
    if _pinecone_client is None:
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable not set")
        _pinecone_client = Pinecone(api_key=api_key)
    return _pinecone_client


def get_openai_client() -> AsyncOpenAI:
    """Get or create OpenAI client for embeddings"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


async def initialize_index():
    """Initialize Pinecone index if it doesn't exist"""
    try:
        pc = get_pinecone_client()

        # Check if index exists
        existing_indexes = pc.list_indexes()
        index_names = [idx.name for idx in existing_indexes]

        if INDEX_NAME not in index_names:
            logger.info(f"Creating Pinecone index: {INDEX_NAME}")
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"  # Change based on your region preference
                )
            )
            logger.info(f"Pinecone index {INDEX_NAME} created")
        else:
            logger.info(f"Pinecone index {INDEX_NAME} already exists")

    except Exception as e:
        logger.error(f"Failed to initialize Pinecone index: {e}")
        raise


def get_index():
    """Get Pinecone index"""
    pc = get_pinecone_client()
    return pc.Index(INDEX_NAME)


async def embed_text(text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI.

    Args:
        text: Text to embed

    Returns:
        List of floats representing the embedding vector
    """
    try:
        client = get_openai_client()
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise


async def store_message_vector(
    chat_id: str,
    message_id: str,
    content: str,
    role: str,
    reasoning_trace: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
):
    """
    Store a message in the vector store.

    Args:
        chat_id: Chat ID (used as namespace)
        message_id: Unique message ID
        content: Message content
        role: Message role (user/assistant)
        reasoning_trace: Optional reasoning trace
        attachments: Optional list of attachment metadata
    """
    if not is_configured():
        return

    try:
        # Build full text to embed: content + reasoning + attachment info
        text_to_embed = content

        if reasoning_trace:
            text_to_embed += f"\n\n[Reasoning]\n{reasoning_trace}"

        if attachments:
            for att in attachments:
                text_to_embed += f"\n\n[Attachment: {att.get('file_name', 'unknown')}]"

        # Generate embedding
        embedding = await embed_text(text_to_embed)

        # Store in Pinecone with metadata
        index = get_index()
        index.upsert(
            vectors=[{
                "id": message_id,
                "values": embedding,
                "metadata": {
                    "chat_id": chat_id,
                    "role": role,
                    "content": content[:1000],  # Truncate for metadata size limits
                    "has_reasoning": bool(reasoning_trace),
                    "has_attachments": bool(attachments),
                }
            }],
            namespace=chat_id  # Each chat has its own namespace
        )

        logger.info(f"Stored vector for message {message_id} in namespace {chat_id}")

    except Exception as e:
        logger.error(f"Failed to store message vector: {e}")
        # Don't raise - vector storage failures shouldn't break message creation


async def query_relevant_context(
    chat_id: str,
    query_text: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query the vector store for relevant context.

    Args:
        chat_id: Chat ID (namespace to query)
        query_text: Query text to find relevant messages
        top_k: Number of results to return

    Returns:
        List of dicts with message metadata and similarity scores
    """
    if not is_configured():
        return []

    try:
        # Generate embedding for query
        query_embedding = await embed_text(query_text)

        # Query Pinecone
        index = get_index()
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=chat_id,
            include_metadata=True
        )

        # Format results
        context_items = []
        for match in results.matches:
            context_items.append({
                "message_id": match.id,
                "score": match.score,
                "metadata": match.metadata
            })

        logger.info(f"Retrieved {len(context_items)} context items for chat {chat_id}")
        return context_items

    except Exception as e:
        logger.error(f"Failed to query vector store: {e}")
        return []


async def merge_vector_namespaces(
    source_chat_ids: List[str],
    target_chat_id: str,
) -> bool:
    """
    Merge vectors from multiple source namespaces into a new target namespace.

    This copies all vectors from source chats into the merged chat's namespace,
    allowing RAG retrieval across all source conversations.

    Args:
        source_chat_ids: List of source chat IDs (namespaces)
        target_chat_id: Target chat ID (new namespace)

    Returns:
        True if successful, False otherwise
    """
    if not is_configured():
        return False

    try:
        index = get_index()
        total_copied = 0

        for source_id in source_chat_ids:
            try:
                # Fetch all vectors from source namespace
                # Pinecone doesn't have a direct "copy namespace" operation,
                # so we need to fetch and re-upsert with new namespace

                # Query with a dummy vector to get all vectors
                # (This is a limitation - for large namespaces, we'd need pagination)
                dummy_vector = [0.0] * EMBEDDING_DIMENSION
                results = index.query(
                    vector=dummy_vector,
                    top_k=10000,  # Max results per query
                    namespace=source_id,
                    include_metadata=True,
                    include_values=True
                )

                if not results.matches:
                    continue

                # Prepare vectors for upsert to target namespace
                vectors_to_upsert = []
                for match in results.matches:
                    # Generate new ID to avoid conflicts
                    new_id = f"{source_id}_{match.id}"

                    # Update metadata to indicate source
                    metadata = match.metadata or {}
                    metadata["source_chat_id"] = source_id
                    metadata["original_chat_id"] = metadata.get("chat_id", source_id)
                    metadata["chat_id"] = target_chat_id  # Update to target

                    vectors_to_upsert.append({
                        "id": new_id,
                        "values": match.values,
                        "metadata": metadata
                    })

                # Upsert to target namespace in batches
                batch_size = 100
                for i in range(0, len(vectors_to_upsert), batch_size):
                    batch = vectors_to_upsert[i:i + batch_size]
                    index.upsert(vectors=batch, namespace=target_chat_id)
                    total_copied += len(batch)

                logger.info(f"Copied {len(vectors_to_upsert)} vectors from {source_id} to {target_chat_id}")

            except Exception as e:
                logger.error(f"Failed to copy vectors from {source_id}: {e}")
                continue

        logger.info(f"Merge complete: {total_copied} total vectors in namespace {target_chat_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to merge vector namespaces: {e}")
        return False


async def delete_namespace(chat_id: str):
    """
    Delete all vectors in a namespace (when deleting a chat).

    Args:
        chat_id: Chat ID (namespace to delete)
    """
    try:
        index = get_index()
        index.delete(delete_all=True, namespace=chat_id)
        logger.info(f"Deleted namespace {chat_id}")
    except Exception as e:
        logger.error(f"Failed to delete namespace {chat_id}: {e}")


async def get_namespace_stats(chat_id: str) -> Dict[str, Any]:
    """
    Get statistics about a namespace.

    Args:
        chat_id: Chat ID (namespace)

    Returns:
        Dict with stats (vector count, etc.)
    """
    try:
        index = get_index()
        stats = index.describe_index_stats()

        namespace_stats = stats.namespaces.get(chat_id, {})

        return {
            "vector_count": namespace_stats.get("vector_count", 0)
        }
    except Exception as e:
        logger.error(f"Failed to get namespace stats: {e}")
        return {"vector_count": 0}
