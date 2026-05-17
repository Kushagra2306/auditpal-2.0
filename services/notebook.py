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
        """Check if NotebookLM is authenticated."""
        storage_path = Path.home() / ".notebooklm" / "storage_state.json"
        return storage_path.exists()
    
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
                # A fresh client is created per call, so its in-memory
                # conversation cache is empty. NotebookLM's ask() builds the
                # prior-turns payload solely from that cache, so reseed it
                # from the app's transcript before continuing a conversation.
                if conversation_id and history:
                    for turn_number, (prev_q, prev_a) in enumerate(history, start=1):
                        client._core.cache_conversation_turn(
                            conversation_id, prev_q, prev_a, turn_number
                        )
                result = await client.chat.ask(
                    notebook_id, question, conversation_id=conversation_id
                )
                references = [
                    {
                        "citation_number": ref.citation_number,
                        "source_id": ref.source_id,
                        "cited_text": ref.cited_text,
                    }
                    for ref in result.references
                ]
                return result.answer, result.conversation_id, references
        return self._run_async(_ask())
