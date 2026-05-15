# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install dependencies**
```bash
uv sync
```

**Run Python files**
Always use `uv run` to execute Python files — never call `python` or `python3` directly:
```bash
uv run script.py
uv run python script.py
```

**Run the application** (from repo root — Windows users must use Git Bash)
```bash
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app is then available at `http://localhost:8000` and Swagger docs at `http://localhost:8000/docs`.

**Environment setup** — create `.env` in the repo root:
```
ANTHROPIC_API_KEY=your_key_here
```

There is no test suite or linter configured in this project.

## Workflow

**"Save changes"** means: commit all staged files with a subject line ≤150 characters, then push to the current branch.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot. FastAPI serves both the REST API and the static frontend from a single process on port 8000.

### Request lifecycle (query)

1. `frontend/script.js` — `sendMessage()` POSTs `{query, session_id}` to `/api/query`
2. `backend/app.py` — route delegates to `RAGSystem.query()`
3. `backend/rag_system.py` — fetches conversation history from `SessionManager`, then calls `AIGenerator.generate_response()` with the `search_course_content` tool available
4. **Round 1 Claude call** — Claude decides whether to invoke the tool
5. If `stop_reason == "tool_use"`: `ToolManager` calls `CourseSearchTool.execute()` → `VectorStore.search()` → ChromaDB semantic query; results are appended to the message list
6. **Round 2 Claude call** — Claude synthesizes the tool result into a final answer (no tools passed this time)
7. Sources collected from `tool_manager.get_last_sources()` are returned alongside the answer

### Document ingestion (startup)

On server start, `app.py` calls `RAGSystem.add_course_folder("../docs")`:
- `DocumentProcessor` parses `.txt`/`.pdf`/`.docx` files — expects the first 3 lines to be `Course Title:`, `Course Link:`, `Course Instructor:`, followed by lessons delimited by `Lesson N: Title`
- Text is chunked (800 chars, 100 char overlap) into `CourseChunk` objects
- `VectorStore` embeds chunks with `all-MiniLM-L6-v2` and stores them in ChromaDB under two collections: `course_catalog` (metadata) and `course_content` (searchable chunks)
- Already-indexed courses are skipped (idempotent)

### Key configuration knobs (`backend/config.py`)

| Setting | Default | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | LLM used for generation |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 800 / 100 | Document chunking |
| `MAX_RESULTS` | 5 | Vector search result count |
| `MAX_HISTORY` | 2 | Conversation turns kept in memory |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence directory (relative to `backend/`) |

### Session state

`SessionManager` is **in-memory only** — sessions are lost on server restart. It stores the last `MAX_HISTORY * 2` messages as a plain string injected into the system prompt.

### Frontend

Plain HTML/JS/CSS — no build step. FastAPI's `StaticFiles` mount at `/` serves `frontend/` with no-cache headers (`DevStaticFiles` subclass in `app.py`). The JS communicates exclusively via `fetch()` to `/api/query` and `/api/courses`.
