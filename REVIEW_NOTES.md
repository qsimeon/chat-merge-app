# REVIEW_NOTES — chat-merge-app
Date: 2026-04-13
Iteration goal: First run — deeply understand the project and create RALPH.md
Outcome: ✅ achieved

## Work done
- Explored full codebase: AGENTS.md, README.md, CLAUDE.md, backend/main.py, all services, routes, providers, models, frontend store, types, API client, components
- Reviewed git history (20 commits back), Dockerfile, railway.toml, and the single Playwright test file
- Created RALPH.md with: Project Goal, Deliverable type, Audience, Success Criteria, Design Philosophy, Constraints, Current State (95%), Human Actions Needed, Codex Delegation Guide, Iteration Log

## Blockers
None — first-run orientation completed successfully.

## Next iteration: Add test infrastructure and write backend unit tests
The biggest gap is test coverage. Specifically:

1. **Create `frontend/playwright.config.ts`** — currently missing; Playwright tests can't run without it
2. **Verify + update `tests/playwright_full_test.py`** — check if tests still reflect current app behavior (Settings UI, merge flow, RAG toggle)
3. **Add `backend/tests/` directory with pytest unit tests** covering:
   - `chat_service.py` (CRUD operations)
   - `completion_service.py` (message history building, RAG context building)
   - `merge_service.py` (merge logic, vector fusion)
   - `vector_service.py` (is_configured check, graceful degradation)

Start with `playwright.config.ts` and run the existing Playwright test to see what passes/fails. Then use `/codex:rescue` to fix failures and add backend unit tests.

Completion: 95%
