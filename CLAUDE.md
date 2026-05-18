# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AuditPal is a Streamlit UI wrapped around `notebooklm-py`, an **unofficial, reverse-engineered** client for Google NotebookLM. It targets accountants who upload documents to a notebook and need auditable, citation-backed answers. There is one shared Google/NotebookLM account for all users (auth is a stored browser session, not per-user).

## Commands

```bash
pip install -e .                 # install app + deps (use a venv locally)
streamlit run app.py             # run the app -> http://localhost:8501
python -m notebooklm login       # one-time / re-auth: opens browser for Google sign-in
python scripts/live_test.py "<notebook name substring>"   # live end-to-end check (needs credentials)
ruff check . && black .          # lint + format (config in pyproject.toml, line-length 100)
docker-compose up -d --build     # containerised run (see README for credential baking)
```

There is **no unit test suite**. `scripts/live_test.py` is the only test harness and it hits the real NotebookLM API, so it requires valid credentials. It exercises the exact code paths (ask → follow-up with context → citation source fetch) and is the fastest iteration loop when credentials are available (`NOTEBOOKLM_AUTH_JSON`).

## Architecture

Layering is strict — keep it that way:

- **`app.py`** — entry point. Owns *all* `st.session_state` and is the *only* place that calls `NotebookService` and threads conversation/notebook IDs. Defines callback closures (`on_send`, `on_view_source`, etc.) and passes them down.
- **`components/`** — pure render functions (`render_chat`, `render_sidebar`, ...). They take data + callbacks, render UI, and call back. They must not import `notebooklm` or touch the service directly.
- **`services/notebook.py`** — `NotebookService`: a **synchronous** facade over the **async** `notebooklm-py` client. Every method opens a *fresh* `NotebookLMClient` via `from_storage()` and runs it on a reused event loop. The service returns plain dicts/tuples — library types never leak into the UI layer.
- **`config.py`** — pydantic-settings + the `PROMPT_TEMPLATES` / `DOCUMENT_CATEGORIES` dicts the UI renders.

Data flow for a question: `render_chat` → `on_send` (app.py, reads session_state) → `NotebookService.ask` → fresh `NotebookLMClient` → NotebookLM. The answer + enriched citations are stored back into `st.session_state["messages"]`; Streamlit reruns re-render from that list.

## NotebookLM behaviour you must know (hard-won, non-obvious)

The wrapper looks simple but the underlying API has sharp edges that drove most of this codebase's design:

- **Fresh client per call.** `NotebookService` discards the client (and its in-memory conversation cache) after every call. Anything that relied on client-side state across calls does not survive — design around this.
- **Conversation context is server-side only.** NotebookLM keeps memory on the notebook's own server-side conversation thread. The library's inline "conversation history" payload is **ignored by the live backend**. Continuity works by anchoring to the server conversation id: `ask()` adopts the notebook's current thread via `chat.get_conversation_id()` *before* asking when the app has no id yet, and re-fetches it *after* asking to track it (the id scraped from the streamed response is unreliable on newer API builds). `app.py` persists this as `current_conversation_id`.
- **Credentials resolve three ways**, checked by `is_authenticated()`: `NOTEBOOKLM_AUTH_JSON` env var (inline JSON, CI-style) → library `get_storage_path()` (profile path `~/.notebooklm/profiles/default/storage_state.json` on v0.4+, with legacy `~/.notebooklm/storage_state.json` fallback). Never hardcode the legacy path. Sessions expire periodically → the cure is always `notebooklm login` + restart; not a code bug.
- **Citations are deliberately enriched.** The chat API returns only a tiny excerpt per citation. `expand_references()` fetches each cited source's indexed text once (`sources.get_fulltext`), locates the cited passage by its 40-char prefix, and stores a **forward-only** slice (cited passage + succeeding text, *no* preceding context) as `ref["expanded_text"]` for the hover tooltip and citations panel. The "View source" modal separately uses `get_source_fulltext` + `find_citation_context` (which *does* include surrounding context, with highlight).
- **`notebooklm-py` is reverse-engineered** and breaks on Google-side changes. It has a hardcoded build label overridable via the `NOTEBOOKLM_BL` env var; response parsing is best-effort and degrades gracefully (empty references rather than errors). Prefer the library's dedicated RPC methods over scraping streamed responses.

## Conventions

- Branch/commit: develop on the designated feature branch; commit messages explain *why*, not *what*.
- Keep the service layer's return values UI-agnostic (dicts/tuples); do citation/text munging in the service, not in components.
- Streamlit rerun model: `on_send` mutates `st.session_state["messages"]` by reference; switching notebooks or clearing chat resets `messages` and `current_conversation_id` together.
- Docker bakes NotebookLM credentials into the image at build time (`COPY credentials/`); never push that image to a public registry. `scripts/deploy.sh` ships it to EC2 via SSH + docker-compose.
