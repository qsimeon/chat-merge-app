"""
Playwright test configuration.

The tests require both servers running:
  - Frontend: http://localhost:5173 (npm run dev in frontend/)
  - Backend:  http://localhost:8000 (uv run uvicorn main:app in backend/)

Run with:
  cd <project-root>
  playwright install chromium  # first time only
  pytest tests/ -v
"""
# No fixtures needed — playwright_full_test.py manages its own browser lifecycle
