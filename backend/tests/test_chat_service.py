"""Unit tests for app.services.chat_service."""
import pytest

from app.schemas import ChatCreate
from app.services.chat_service import (
    create_chat,
    get_chat,
    get_chats,
    update_chat,
    delete_chat,
    create_message,
    get_messages,
)


async def test_create_chat(db):
    chat_data = ChatCreate(title="My Chat", provider="openai", model="gpt-4o")
    chat = await create_chat(db, chat_data)

    assert chat.id is not None
    assert chat.title == "My Chat"
    assert chat.provider == "openai"
    assert chat.model == "gpt-4o"


async def test_get_chat_not_found(db):
    result = await get_chat(db, "nonexistent-id")
    assert result is None


async def test_get_chats_empty(db):
    chats = await get_chats(db)
    assert chats == []


async def test_update_chat_title(db):
    chat_data = ChatCreate(title="Original Title", provider="anthropic", model="claude-3-5-sonnet-20241022")
    chat = await create_chat(db, chat_data)

    updated = await update_chat(db, chat.id, {"title": "New Title"})
    assert updated is not None
    assert updated.title == "New Title"


async def test_delete_chat(db):
    chat_data = ChatCreate(title="To Delete", provider="openai", model="gpt-4o")
    chat = await create_chat(db, chat_data)

    result = await delete_chat(db, chat.id, pinecone_key=None)
    assert result is True

    # Second delete should return False
    result2 = await delete_chat(db, chat.id, pinecone_key=None)
    assert result2 is False


async def test_create_message(db):
    chat_data = ChatCreate(title="Chat With Messages", provider="openai", model="gpt-4o")
    chat = await create_chat(db, chat_data)

    message = await create_message(db, chat.id, role="user", content="Hello!")
    assert message is not None
    assert message.role == "user"
    assert message.content == "Hello!"
    assert message.chat_id == chat.id


async def test_create_message_nonexistent_chat(db):
    result = await create_message(db, "bad-chat-id", role="user", content="Won't work")
    assert result is None


async def test_get_messages(db):
    chat_data = ChatCreate(title="Message Order Test", provider="gemini", model="gemini-2.0-flash")
    chat = await create_chat(db, chat_data)

    msg1 = await create_message(db, chat.id, role="user", content="First message")
    msg2 = await create_message(db, chat.id, role="assistant", content="Second message")

    messages = await get_messages(db, chat.id)
    assert len(messages) == 2
    # Both messages should be present (order by created_at)
    contents = [m.content for m in messages]
    assert "First message" in contents
    assert "Second message" in contents
