# Codebase Intelligence Platform

A dynamic AI-powered repository intelligence workspace. Paste **any public GitHub repository URL** and the application fetches that repository's real metadata and source files, then powers the dashboard from the analysis.

## What is dynamic

Nothing in the workspace is hardcoded to CodeRoom. For each repository the app computes:

- repository metadata, branch, stars, forks and topics
- indexed files, lines and language distribution
- detected technologies/frameworks
- directory/module signals and likely entrypoints
- repository-local import/dependency graph
- interactive architecture visualization
- knowledge graph view
- dependency explorer
- impact analysis for a file/symbol/path
- heuristic system-flow discovery
- source-grounded AI codebase chat with conversation history
- one-click file summaries generated from the actual indexed source
- email/password signup, login, logout and persistent profile editing
- generated architecture/documentation notes
- latest two-commit architecture-change comparison when GitHub exposes it

CodeRoom can be used as a demo repository, but it is not embedded in the application.

## Stack

**Web:** Next.js 15, React 19, TypeScript, Framer Motion, React Three Fiber, Three.js, Lucide

**API:** FastAPI, HTTPX, NumPy, optional Sentence Transformers, optional OpenAI

**Analysis:** GitHub REST API, repository-local import parsing, in-memory vector retrieval, heuristic impact/flow analysis

## Run locally

### Frontend

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

### Backend

Use **Python 3.10+ (3.11 recommended)**.

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for API docs.

### Environment

For the API, copy `apps/api/.env.example` to `apps/api/.env` and set values as needed. The API loads that file automatically. For the web app, copy `apps/web/.env.example` to `apps/web/.env.local`.

- `GITHUB_TOKEN` is optional, but increases GitHub API rate limits.
- `OPENAI_API_KEY` is optional. For genuinely conversational, repository-grounded answers, set it in `apps/api/.env`. Without it, the app uses deterministic retrieval-grounded fallback responses.
- `OPENAI_MODEL` controls the chat/file-summary model; `gpt-4.1-mini` is the default.
- `OPENAI_MODEL` defaults to `gpt-4.1-mini`.

For the frontend, `apps/web/.env.example` contains `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Optional semantic embeddings

The current retrieval layer works without a downloaded embedding model so first-run setup remains light. For transformer embeddings, install:

```powershell
pip install sentence-transformers==3.4.1
```

The backend automatically uses `all-MiniLM-L6-v2` when the package/model is available and falls back otherwise.

## Docker

```powershell
docker compose up --build
```

Frontend: `http://localhost:3000`  
Backend: `http://localhost:8000`

## UI and workspace

The UI uses the `#1D4533 / #F7EAE0 / #F9D2BA / #5E3122` palette with restrained glass surfaces. The architecture view uses a readable 3D topology with source-file labels, repository-local import edges, and a slowly rotating polygon wireframe. Motion is intentionally limited to useful state changes and can be reduced from Profile & settings.

The Profile & settings panel is backed by FastAPI + SQLite authentication for local development. Accounts use hashed passwords and opaque session tokens. For production, move auth/session storage to a managed database and secure secret store.

## Important scope notes

This project intentionally analyzes **public GitHub repositories**. Private repositories require a valid GitHub token with appropriate access and are not enabled by the public-URL UI alone.

Impact analysis and system-flow discovery are engineering heuristics based on the indexed source tree. They are decision-support signals, not a compiler-level guarantee of every runtime dependency.
