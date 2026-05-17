"""NotebookLM service wrapper for AuditPal."""

import asyncio
from pathlib import Path
from typing import List
from dataclasses import dataclass


@dataclass
class Source:
    """Represents a source in a notebook."""
    id: str
    title: str
    source_type: str
    category: str = "other"


class NotebookService:
    """Service for interacting with NotebookLM."""
    
    def __init__(self):
        """Initialize the service."""
        self._loop = None
    
    def _get_loop(self):
        """Get or create event loop."""
        try:
            self._loop = asyncio.get_event_loop()
            if self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    def _run_async(self, coro):
        """Run async coroutine synchronously."""
        loop = self._get_loop()
        return loop.run_until_complete(coro)
    
    def is_authenticated(self) -> bool:
        """Check if NotebookLM is authenticated.

        Accepts the CI-style ``NOTEBOOKLM_AUTH_JSON`` env var (inline
        credentials, no file) and otherwise resolves the credentials path
        via the library itself so this check matches wherever
        ``notebooklm login`` saved them (newer versions use profile-based
        paths like ``~/.notebooklm/profiles/default/storage_state.json``).
        """
        import os
        if os.environ.get("NOTEBOOKLM_AUTH_JSON", "").strip():
            return True
        try:
            from notebooklm.paths import get_storage_path
            return get_storage_path().exists()
        except Exception:
            legacy = Path.home() / ".notebooklm" / "storage_state.json"
            return legacy.exists()
    
    def list_notebooks(self) -> List[dict]:
        """List all notebooks."""
        async def _list():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                notebooks = await client.notebooks.list()
                return [{"id": nb.id, "title": nb.title} for nb in notebooks]
        return self._run_async(_list())
    
    def create_notebook(self, title: str) -> dict:
        """Create a new notebook."""
        async def _create():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                nb = await client.notebooks.create(title)
                return {"id": nb.id, "title": nb.title}
        return self._run_async(_create())
    
    def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        async def _delete():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                await client.notebooks.delete(notebook_id)
                return True
        return self._run_async(_delete())
    
    def list_sources(self, notebook_id: str) -> List[Source]:
        """List sources in a notebook."""
        async def _list():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                sources = await client.sources.list(notebook_id)
                return [Source(id=s.id, title=s.title, source_type=getattr(s, 'type', 'unknown')) 
                        for s in sources]
        return self._run_async(_list())
    
    def add_url_source(self, notebook_id: str, url: str, wait: bool = True) -> dict:
        """Add a URL source to notebook."""
        async def _add():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                result = await client.sources.add_url(notebook_id, url, wait=wait)
                return {"id": getattr(result, 'id', None), "status": "added"}
        return self._run_async(_add())
    
    def add_file_source(self, notebook_id: str, file_path: Path, wait: bool = True) -> dict:
        """Add a file source to notebook."""
        async def _add():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                result = await client.sources.add_file(notebook_id, str(file_path), wait=wait)
                return {"id": getattr(result, 'id', None), "status": "added"}
        return self._run_async(_add())
    
    def delete_source(self, notebook_id: str, source_id: str) -> bool:
        """Delete a source from notebook."""
        async def _delete():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                await client.sources.delete(notebook_id, source_id)
                return True
        return self._run_async(_delete())
    
    def ask(
        self,
        notebook_id: str,
        question: str,
        conversation_id: str | None = None,
        history: List[tuple[str, str]] | None = None,
    ) -> tuple[str, str | None, List[dict]]:
        """Ask a question about the sources.

        Pass conversation_id from a previous call together with history
        (oldest-first (question, answer) pairs) to continue the same
        conversation so NotebookLM has prior turns as context.

        Returns:
            Tuple of (answer, conversation_id, references). Each reference is
            a dict with keys: citation_number, source_id, cited_text.
        """
        async def _ask():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                # NotebookLM keeps conversation memory server-side, tied to
                # the notebook's existing conversation thread. If the app has
                # no conversation id yet, adopt the notebook's current
                # server-side thread instead of letting the library mint a
                # fresh uuid (the server treats unknown ids as ephemeral and
                # never persists those turns, so follow-ups lose context).
                effective_conv_id = conversation_id
                if effective_conv_id is None:
                    try:
                        effective_conv_id = await client.chat.get_conversation_id(
                            notebook_id
                        )
                    except Exception:
                        effective_conv_id = None
                # Also seed the in-memory cache so the library still emits the
                # inline prior-turns payload (harmless if the backend ignores
                # it; helps if it does not).
                if effective_conv_id and history:
                    for turn_number, (prev_q, prev_a) in enumerate(history, start=1):
                        client._core.cache_conversation_turn(
                            effective_conv_id, prev_q, prev_a, turn_number
                        )
                result = await client.chat.ask(
                    notebook_id, question, conversation_id=effective_conv_id
                )
                # The streamed conversation id can be missed on newer API
                # builds; prefer the authoritative id from the dedicated RPC
                # so the next turn threads into the same server-side
                # conversation.
                resolved_conv_id = result.conversation_id
                try:
                    server_id = await client.chat.get_conversation_id(notebook_id)
                    if server_id:
                        resolved_conv_id = server_id
                except Exception:
                    pass
                references = [
                    {
                        "citation_number": ref.citation_number,
                        "source_id": ref.source_id,
                        "cited_text": ref.cited_text,
                    }
                    for ref in result.references
                ]
                return result.answer, resolved_conv_id, references
        return self._run_async(_ask())

    def get_source_fulltext(
        self,
        notebook_id: str,
        source_id: str,
        cited_text: str | None = None,
    ) -> dict:
        """Fetch the full indexed text of a source for citation auditing.

        Returns a dict with the source title, full content, char count, and
        (when cited_text is given) the located passages with surrounding
        context so the exact cited chunk can be shown in the source.
        """
        async def _get():
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                ft = await client.sources.get_fulltext(notebook_id, source_id)
                contexts = []
                if cited_text:
                    for ctx, pos in ft.find_citation_context(cited_text):
                        contexts.append({"context": ctx, "position": pos})
                return {
                    "title": ft.title,
                    "content": ft.content,
                    "char_count": ft.char_count,
                    "contexts": contexts,
                }
        return self._run_async(_get())
