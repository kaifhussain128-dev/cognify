# Project Guidelines & Rules

## Security & Secrets Protection

- **Do NOT read or access `.env`**: Under no circumstances should the agent use any tool to inspect, read, print, display, or edit the `.env` file or any `.env.*` / secret credential files.
- **Do NOT expose secrets**: Never print or leak secret keys, tokens, or contents from environment variable files in tool outputs, responses, or artifacts.
- **File Listings**: When listing or summarizing the files in this repository, exclude `.env` and any secret files from the output.

## Commands

- Install deps: `venv\Scripts\python.exe -m pip install -r requirements.txt` (`venv\Scripts\pip.exe` is a broken shim here — always use `python -m pip`; the venv ships with only pip)
- Run locally (from repo root): `uvicorn backend.main:app --host 0.0.0.0 --port 8000`, then open http://localhost:8000
- Smoke tests: `python test_sessions.py` (SQLite layer + FastAPI TestClient; needs `httpx`, `fastapi` from requirements)
- No lint, format, typecheck, or CI config exists in the repo.

## Environment

- `GEMINI_API_KEY` — required; loaded from `.env` via python-dotenv in `backend/main.py` (or set in the Render dashboard)
- `GROQ_API_KEY` — optional; enables the Groq engine in Fast AI Search
- `GEMINI_MODEL` — optional; defaults to `gemini-3.6-flash` on `/api/study`, but `gemini-3-flash-preview` on the legacy `/ask-ai`
- `GOOGLE_CLIENT_ID` — optional; enables real Google OAuth sign-in (Google Identity Services). Without it, `/auth/google` returns 503 and the UI shows a "not configured" note; `/api/config` exposes the public client ID to the SPA

## Architecture

- One FastAPI app (`backend/main.py`) serves both the API and the entire frontend — `frontend/index.html` is a single-file vanilla-JS SPA with no build step; all fetches are same-origin relative paths.
- `backend/auth.py` — SQLite users/sessions/login_logs/site_visits; `init_db()` runs at import time and creates/migrates `backend/cognify.db`; seeds a default admin account (credentials live in `init_db`, email `admin@cognify.ai`).
- `backend/sessions_db.py` — study_sessions/session_messages tables, also DDL-at-import; session IDs are client-generated (`sess_<ms>`); the first user message auto-creates the session and derives its title from the prompt.
- `backend/pdf_processor.py` — pypdf text extraction plus a rule-based "Parsli-style" structured extractor (no AI quota).
- `backend/fast_search.py` — engine routing for `auto|web|doc|groq|gemini`; `web` = Wikipedia + DuckDuckGo (keyless); failover chain Groq → Gemini → local heuristic.
- `main.py` inserts `backend/` into `sys.path`, so `uvicorn backend.main:app` must be run from the repo root.

## Gotchas

- Importing any backend module touches `backend/cognify.db` (schema DDL at import). `*.db` and `data/*.pdf` are gitignored.
- `test_sessions.py` mutates the real local DB: it registers a throwaway user (persists) and logs in as the seeded admin; test sessions are deleted but the user row stays.
- `/api/study` requires a valid `token` (401 otherwise); legacy `/ask-ai` and `/api/sage` do not.
- `generate_summary_pdf.py` imports `reportlab`, which is NOT in `requirements.txt` — install it separately if you use that script.
- Local venv is Python 3.14; `render.yaml` pins Python 3.11.9.
- Deploy: Render via `render.yaml` (build `pip install -r requirements.txt`, start `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, `GEMINI_API_KEY` set in dashboard). `deploy.bat` pushes to GitHub and opens the Render dashboard; full steps in `DEPLOYMENT.md`. A `Procfile` also exists for Heroku-style hosts.
- Git: `main` branch, remote `github.com/kaifhussain128-dev/cognify.git`; no PR/CI workflow.
- `GEMINI.md` is an exact duplicate of this file — keep both in sync.
