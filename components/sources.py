"""Source management component for AuditPal."""

import streamlit as st
from typing import List, Callable
from pathlib import Path
import tempfile

from config import DOCUMENT_CATEGORIES


def render_sources(
    sources: List,
    on_add_url: Callable,
    on_add_file: Callable,
    on_delete: Callable,
    supported_extensions: List[str],
    allow_modify: bool = True
):
    """Render the source management interface.

    When ``allow_modify`` is False (market-test lock) the upload/URL tabs
    and per-source delete are hidden — the source list is read-only.
    """

    st.markdown("## 📁 Sources")
    st.caption(
        "Documents in this workspace" if not allow_modify
        else "Add documents and URLs to analyze"
    )

    if not allow_modify:
        _render_source_list(sources, on_delete, allow_modify=False)
        return

    # Add sources section
    tab1, tab2 = st.tabs(["📤 Upload Files", "🔗 Add URL"])
    
    with tab1:
        uploaded_files = st.file_uploader(
            "Upload documents",
            type=[ext.lstrip('.') for ext in supported_extensions],
            accept_multiple_files=True,
            help="Supported: PDF, Word, Text, Markdown, Excel, CSV"
        )
        
        if uploaded_files:
            # Category selection
            category = st.selectbox(
                "Categorize as",
                options=list(DOCUMENT_CATEGORIES.keys()),
                format_func=lambda x: f"{DOCUMENT_CATEGORIES[x]['icon']} {DOCUMENT_CATEGORIES[x]['name']}"
            )
            
            if st.button("📤 Upload Selected Files", use_container_width=True):
                with st.spinner("Uploading files..."):
                    for uploaded_file in uploaded_files:
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=Path(uploaded_file.name).suffix
                        ) as tmp:
                            tmp.write(uploaded_file.getbuffer())
                            tmp_path = Path(tmp.name)
                        
                        try:
                            on_add_file(tmp_path, category)
                            st.success(f"✅ Added: {uploaded_file.name}")
                        except Exception as e:
                            st.error(f"❌ Failed to add {uploaded_file.name}: {e}")
                        finally:
                            tmp_path.unlink(missing_ok=True)
    
    with tab2:
        url = st.text_input(
            "Enter URL",
            placeholder="https://example.com/document.pdf",
            help="Supports web pages, PDFs, YouTube videos"
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            url_category = st.selectbox(
                "Category",
                options=list(DOCUMENT_CATEGORIES.keys()),
                format_func=lambda x: f"{DOCUMENT_CATEGORIES[x]['icon']} {DOCUMENT_CATEGORIES[x]['name']}",
                key="url_category"
            )
        with col2:
            st.write("")  # Spacing
            st.write("")
            if st.button("🔗 Add URL", disabled=not url):
                with st.spinner("Adding URL..."):
                    try:
                        on_add_url(url, url_category)
                        st.success(f"✅ Added URL")
                    except Exception as e:
                        st.error(f"❌ Failed: {e}")
    
    st.divider()
    _render_source_list(sources, on_delete, allow_modify=True)


def _render_source_list(sources: List, on_delete: Callable, allow_modify: bool):
    """Render the grouped source list (read-only when allow_modify=False)."""
    st.markdown("### 📚 Current Sources")

    if not sources:
        msg = ("No sources in this workspace yet." if not allow_modify
               else "No sources added yet. Upload files or add URLs above.")
        st.info(msg)
        return

    # Group by category
    categorized = {}
    for source in sources:
        cat = getattr(source, 'category', 'other')
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(source)

    for cat_key, cat_sources in categorized.items():
        cat_info = DOCUMENT_CATEGORIES.get(cat_key, DOCUMENT_CATEGORIES['other'])

        with st.expander(
            f"{cat_info['icon']} {cat_info['name']} ({len(cat_sources)})",
            expanded=True
        ):
            for source in cat_sources:
                if not allow_modify:
                    st.markdown(f"📄 **{source.title}**")
                    st.caption(f"Type: {source.source_type}")
                    continue
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"📄 **{source.title}**")
                    st.caption(f"Type: {source.source_type}")
                with col2:
                    if st.button("🗑️", key=f"del_{source.id}", help="Delete source"):
                        on_delete(source.id)
                        st.rerun()
