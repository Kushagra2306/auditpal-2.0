"""
AuditPal - AI-powered document assistant for accountants.
Built on NotebookLM.
"""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings
from services.notebook import NotebookService
from components.sidebar import render_sidebar
from components.sources import render_sources
from components.chat import render_chat
from utils.export import export_to_markdown, export_to_pdf, get_download_filename


# Page config
st.set_page_config(
    page_title="AuditPal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1400px;
        margin: 0 auto;
    }
    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)


def _conversation_history(messages):
    """Reconstruct oldest-first (question, answer) pairs from the transcript.

    A trailing user message with no answer (the question currently being
    asked) and any failed turns are excluded so they don't poison context.
    """
    pairs = []
    pending_q = None
    for msg in messages:
        if msg["role"] == "user":
            pending_q = msg["content"]
        elif msg["role"] == "assistant" and pending_q is not None:
            answer = msg["content"]
            if not answer.startswith("❌ Error:"):
                pairs.append((pending_q, answer))
            pending_q = None
    return pairs


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "messages": [],
        "current_notebook_id": None,
        "current_conversation_id": None,
        "sources": [],
        "notebooks": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_setup_page(service: NotebookService):
    """Render the NotebookLM setup page."""
    st.markdown("# 📊 AuditPal")
    st.markdown("### Your AI-powered accounting document assistant")

    st.markdown("""
    ---

    **What you can do with AuditPal:**
    - 📤 Upload tax forms, financial statements, and client documents
    - 💬 Ask questions and get instant answers about your documents
    - 🔍 Find discrepancies and red flags automatically
    - 📋 Use pre-built templates for common accounting tasks
    - 📥 Export your analysis to PDF or Markdown

    ---
    """)

    st.warning("⚠️ NotebookLM not connected yet.")

    st.markdown("""
    ### 🔗 Admin Setup Required (One-time)

    Run these commands on your **local machine** (not in Docker):
    """)

    st.code("""pip install "notebooklm-py[browser]"
playwright install chromium
notebooklm login""", language="bash")

    st.markdown("""
    A browser will open. Sign in with your Google account.

    After signing in, **restart Docker** to pick up the credentials:
    """)

    st.code("docker-compose down && docker-compose up -d", language="bash")

    if st.button("🔄 Check Connection", use_container_width=True, type="primary"):
        if service.is_authenticated():
            st.success("✅ Connected! Refreshing...")
            st.rerun()
        else:
            st.error("Not connected yet. Please complete the login and restart Docker.")


def render_main_app(service: NotebookService, settings):
    """Render the main application."""
    # Load notebooks
    try:
        if not st.session_state["notebooks"]:
            st.session_state["notebooks"] = service.list_notebooks()
    except Exception as e:
        st.error(f"Failed to load notebooks: {e}")
        st.session_state["notebooks"] = []

    # Callbacks
    def on_notebook_select(notebook_id):
        st.session_state["current_notebook_id"] = notebook_id
        st.session_state["messages"] = []
        st.session_state["current_conversation_id"] = None
        st.session_state["sources"] = service.list_sources(notebook_id)

    def on_notebook_create(title):
        nb = service.create_notebook(title)
        st.session_state["notebooks"].append(nb)
        on_notebook_select(nb["id"])
        st.success(f"Created notebook: {title}")

    # Render sidebar
    render_sidebar(
        notebooks=st.session_state["notebooks"],
        current_notebook_id=st.session_state["current_notebook_id"],
        on_notebook_select=on_notebook_select,
        on_notebook_create=on_notebook_create,
    )

    # Main content
    if not st.session_state["current_notebook_id"]:
        st.markdown("# 📊 Welcome to AuditPal")
        st.info("👈 Create or select a notebook from the sidebar to get started.")
        return

    # Two-column layout
    col1, col2 = st.columns([1, 2])

    with col1:
        # Source callbacks
        def on_add_url(url, category):
            service.add_url_source(st.session_state["current_notebook_id"], url)
            st.session_state["sources"] = service.list_sources(
                st.session_state["current_notebook_id"]
            )

        def on_add_file(file_path, category):
            service.add_file_source(st.session_state["current_notebook_id"], file_path)
            st.session_state["sources"] = service.list_sources(
                st.session_state["current_notebook_id"]
            )

        def on_delete_source(source_id):
            service.delete_source(st.session_state["current_notebook_id"], source_id)
            st.session_state["sources"] = service.list_sources(
                st.session_state["current_notebook_id"]
            )

        render_sources(
            sources=st.session_state["sources"],
            on_add_url=on_add_url,
            on_add_file=on_add_file,
            on_delete=on_delete_source,
            supported_extensions=settings.supported_extensions
        )

    with col2:
        # Chat callbacks
        def on_send(message):
            sent_conv_id = st.session_state.get("current_conversation_id")
            hist = _conversation_history(st.session_state["messages"])
            answer, conv_id, refs = service.ask(
                st.session_state["current_notebook_id"],
                message,
                conversation_id=sent_conv_id,
                history=hist,
            )
            st.session_state["current_conversation_id"] = conv_id
            st.session_state["_debug_last"] = {
                "sent_conversation_id": sent_conv_id,
                "returned_conversation_id": conv_id,
                "history_pairs_sent": len(hist),
            }

            sources_by_id = {s.id: s.title for s in st.session_state["sources"]}
            for ref in refs:
                ref["source_title"] = sources_by_id.get(
                    ref["source_id"], "Unknown source"
                )
            return {"answer": answer, "references": refs}

        def on_clear():
            st.session_state["messages"] = []
            st.session_state["current_conversation_id"] = None

        def on_export(format):
            notebook_title = "AuditPal Chat"
            for nb in st.session_state["notebooks"]:
                if nb["id"] == st.session_state["current_notebook_id"]:
                    notebook_title = nb["title"]
                    break

            if format == "markdown":
                content = export_to_markdown(st.session_state["messages"], notebook_title)
                filename = get_download_filename(notebook_title, "md")
                st.download_button("📥 Download", content, filename, "text/markdown")
            elif format == "pdf":
                content = export_to_pdf(st.session_state["messages"], notebook_title)
                filename = get_download_filename(notebook_title, "pdf")
                st.download_button("📥 Download", content, filename, "application/pdf")

        has_sources = len(st.session_state["sources"]) > 0
        render_chat(
            messages=st.session_state["messages"],
            on_send=on_send,
            on_clear=on_clear,
            on_export=on_export,
            disabled=not has_sources
        )

        with st.expander("🔧 Debug: conversation state", expanded=False):
            st.write({
                "current_conversation_id": st.session_state.get(
                    "current_conversation_id"
                ),
                "last_request": st.session_state.get("_debug_last", "no requests yet"),
            })


def main():
    """Main application entry point."""
    init_session_state()
    settings = get_settings()

    # Initialize NotebookLM service (single account for all users)
    service = NotebookService()

    # Check if NotebookLM is authenticated
    if not service.is_authenticated():
        render_setup_page(service)
    else:
        render_main_app(service, settings)


if __name__ == "__main__":
    main()
