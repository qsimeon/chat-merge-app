"""Unit tests for app.services.vector_service — no real API keys needed."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services import vector_service


def test_is_configured_returns_false():
    assert vector_service.is_configured() is False


async def test_embed_text_no_keys_raises():
    with pytest.raises(ValueError, match="neither openai_key nor gemini_key provided"):
        await vector_service.embed_text("hello")


async def test_store_message_vector_no_pinecone_key_noop():
    # Should return silently without raising
    await vector_service.store_message_vector(
        chat_id="chat-1",
        message_id="msg-1",
        content="test",
        role="user",
        pinecone_key="",
        openai_key=None,
        gemini_key=None,
    )


async def test_query_relevant_context_no_keys_returns_empty():
    result = await vector_service.query_relevant_context(
        chat_id="chat-1",
        query_text="hello",
        pinecone_key="",
        openai_key=None,
        gemini_key=None,
    )
    assert result == []


async def test_get_namespace_stats_no_key_returns_zero():
    result = await vector_service.get_namespace_stats("chat-1", pinecone_key="")
    assert result == {"vector_count": 0}


async def test_delete_namespace_no_key_noop():
    # Should return silently without raising
    await vector_service.delete_namespace("chat-1", pinecone_key="")


async def test_fuse_namespaces_all_empty_returns_zero():
    mock_index = MagicMock()
    # index.list() returns an empty iterator
    mock_index.list.return_value = iter([])

    with patch.object(vector_service, "_get_pinecone_index", return_value=mock_index), \
         patch.object(vector_service, "ensure_index_exists", new_callable=AsyncMock):
        result = await vector_service.fuse_namespaces(
            source_chat_ids=["chat-a", "chat-b"],
            target_chat_id="chat-merged",
            pinecone_key="fake-key",
        )

    assert result == {"fused": 0, "kept": 0, "total": 0}
