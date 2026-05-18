"""Sidebar component for AuditPal."""

import streamlit as st
from typing import Optional, List


def render_sidebar(
    notebooks: List[dict],
    current_notebook_id: Optional[str],
    on_notebook_select,
    on_notebook_create,
    locked: bool = False,
    feedback_url: str = "",
):
    """Render the sidebar with notebook selection.

    When ``locked`` (market-test mode) the tester is pinned to a single
    assigned notebook: notebook creation and selection are hidden.
    """

    with st.sidebar:
        # App header
        st.markdown("## 📊 AuditPal")
        st.caption("AI-powered document assistant")

        st.divider()

        # Notebook section
        st.markdown("### 📓 Workspace" if locked else "### 📓 Notebooks")

        if locked:
            title = notebooks[0]["title"] if notebooks else "Demo workspace"
            st.markdown(f"**{title}**")
            st.caption("You are in your assigned demo workspace.")
        else:
            # Create new notebook
            with st.expander("➕ Create New Notebook"):
                new_notebook_name = st.text_input(
                    "Notebook name",
                    placeholder="e.g., Q1 2024 Tax Review",
                    key="new_notebook_name"
                )
                if st.button("Create", use_container_width=True, disabled=not new_notebook_name):
                    on_notebook_create(new_notebook_name)

            # List existing notebooks
            if notebooks:
                notebook_options = {nb["title"]: nb["id"] for nb in notebooks}

                # Find current selection
                current_title = None
                for title, nb_id in notebook_options.items():
                    if nb_id == current_notebook_id:
                        current_title = title
                        break

                selected_title = st.selectbox(
                    "Select notebook",
                    options=list(notebook_options.keys()),
                    index=list(notebook_options.keys()).index(current_title) if current_title else 0,
                    key="notebook_select"
                )

                if selected_title and notebook_options[selected_title] != current_notebook_id:
                    on_notebook_select(notebook_options[selected_title])
            else:
                st.info("No notebooks yet. Create one to get started!")

        st.divider()

        # Help section
        with st.expander("❓ Help"):
            st.markdown("""
            **Getting Started:**
            1. Create or select a notebook
            2. Add sources (files or URLs)
            3. Ask questions about your documents

            **Supported Files:**
            - PDF, Word (.docx)
            - Text, Markdown
            - Excel, CSV

            **Tips:**
            - Use templates for common questions
            - Export answers for your records
            """)

        # Footer
        st.divider()
        if feedback_url:
            st.link_button(
                "📝 Give feedback", feedback_url, use_container_width=True
            )
        st.caption("AuditPal v0.1.0")
        st.caption("Powered by NotebookLM")
