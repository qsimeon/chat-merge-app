# REVIEW_NOTES — chat-merge-app
Date: 2026-04-13
Iteration goal: Add backend unit test suite and Playwright test infrastructure
Outcome: ✅ achieved

## Work done
- Added `pytest>=8.0.0` and `pytest-asyncio>=0.23.0` to `backend/pyproject.toml`
- Added `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- Created `backend/tests/conftest.py`: in-memory SQLite async fixtures + `httpx.AsyncClient` test client (overrides per-router `get_db` dependencies)
- Created `backend/tests/test_chat_service.py`: 8 async service-layer tests (CRUD: chats, messages)
- Created `backend/tests/test_vector_service.py`: 7 tests for graceful degradation without API keys + mocked fuse_namespaces empty-namespace case
- Created `backend/tests/test_api_chats.py`: 5 HTTP-level route tests via AsyncClient
- Created `tests/conftest.py`: documentation conftest for Playwright tests (two-server requirement)
- All 20 tests pass in 0.68s with zero real API calls

## Blockers
None.

## Next iteration: Add merge service tests + Playwright e2e smoke test
The test suite covers CRUD and vector service, but the **merge flow** has no test coverage yet.

Concrete goals:
1. **`backend/tests/test_merge_service.py`** — unit tests for `_summarize_conversation`, and mock-based tests for `merge_chats` generator (test that it yields StreamChunk events, creates an empty merged chat, records MergeHistory). Use `unittest.mock` to mock `vector_service.fuse_namespaces` and the provider.
2. **`backend/tests/test_completion_service.py`** — test `_build_message_history` (system role conversion, attachment handling), `_build_merged_chat_context` (mock vector_service.query_relevant_context to return 0 results → no hallucination).
3. **Playwright smoke test**: Verify the existing `tests/playwright_full_test.py` still runs cleanly by:
   - Installing playwright chromium: `playwright install chromium`
   - Starting both servers: `./start.sh`
   - Running: `pytest tests/playwright_full_test.py -v --timeout=120`
   - Document which tests pass and which need updating

Completion: 96%
