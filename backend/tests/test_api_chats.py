"""HTTP-level API tests for /api/chats endpoints."""
import pytest


async def test_get_chats_empty(client):
    response = await client.get("/api/chats/")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_and_get_chat(client):
    # Create a new chat
    payload = {"title": "Test", "provider": "openai", "model": "gpt-4o"}
    create_resp = await client.post("/api/chats/", json=payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["title"] == "Test"
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o"
    chat_id = data["id"]

    # Fetch by id
    get_resp = await client.get(f"/api/chats/{chat_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["id"] == chat_id
    assert fetched["title"] == "Test"


async def test_delete_chat_api(client):
    # Create
    create_resp = await client.post(
        "/api/chats/", json={"title": "Delete Me", "provider": "openai", "model": "gpt-4o"}
    )
    assert create_resp.status_code == 201
    chat_id = create_resp.json()["id"]

    # Delete
    delete_resp = await client.delete(f"/api/chats/{chat_id}")
    assert delete_resp.status_code == 204

    # Now GET should 404
    get_resp = await client.get(f"/api/chats/{chat_id}")
    assert get_resp.status_code == 404


async def test_rename_chat(client):
    # Create
    create_resp = await client.post(
        "/api/chats/", json={"title": "Original", "provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}
    )
    assert create_resp.status_code == 201
    chat_id = create_resp.json()["id"]

    # Rename via PATCH
    patch_resp = await client.patch(f"/api/chats/{chat_id}", json={"title": "renamed"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "renamed"


async def test_get_nonexistent_chat(client):
    response = await client.get("/api/chats/fake-id")
    assert response.status_code == 404
