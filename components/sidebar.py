"""Sidebar component for AuditPal."""

import os
import hmac
import streamlit as st
from typing import Optional, List


def render_sidebar(
    notebooks: List[dict],
    current_notebook_id: Optional[str],
    on_notebook_select,
    on_notebook_create,
    locked: bool = False,
    feedback_url: str = "",
    admin_password: str = "",
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

        # Admin re-auth panel (hidden behind ADMIN_PASSWORD)
        if admin_password:
            _render_admin_panel(admin_password)

        # Footer
        st.divider()
        if feedback_url:
            st.link_button(
                "📝 Give feedback", feedback_url, use_container_width=True
            )
        st.caption("AuditPal v0.1.0")
        st.caption("Powered by NotebookLM")


def _render_admin_panel(admin_password: str) -> None:
    """Collapsible admin panel for refreshing the NotebookLM session in-place.

    Requires the admin to enter ADMIN_PASSWORD first. Once unlocked, they
    paste fresh auth JSON (obtained by running `notebooklm login` locally
    and copying their storage_state.json) and the app writes it to the
    credential path so the next service call picks it up without a restart.
    """
    st.divider()
    with st.expander("🔧 Admin"):
        if not st.session_state.get("_admin_authed"):
            pw = st.text_input("Admin password", type="password", key="_admin_pw")
            if st.button("Unlock", key="_admin_unlock"):
                if hmac.compare_digest(pw or "", admin_password):
                    st.session_state["_admin_authed"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            return

        st.markdown("**Refresh NotebookLM session**")
        st.caption(
            "Run `notebooklm login` on your local machine, then copy the contents "
            "of `~/.notebooklm/storage_state.json` and paste below."
        )
        new_json = st.text_area("Auth JSON", height=120, key="_admin_auth_json",
                                placeholder='{"cookies": [...], ...}')
        if st.button("Apply", type="primary", key="_admin_apply", disabled=not new_json.strip()):
            try:
                import json as _json
                _json.loads(new_json)  # validate before writing
                _write_auth_json(new_json.strip())
                st.success("Session updated. The next request will use the new credentials.")
            except Exception as exc:
                st.error(f"Failed: {exc}")


def _write_auth_json(json_str: str) -> None:
    """Write fresh auth JSON to the path the notebooklm library reads."""
    # Prefer updating NOTEBOOKLM_AUTH_JSON in the process environment so it
    # takes effect immediately without a file-system write (works for the
    # current process and all new Streamlit script threads).
    os.environ["NOTEBOOKLM_AUTH_JSON"] = json_str

    # Also persist to the on-disk storage path so the keepalive thread and
    # any subprocess pick it up after a restart.
    try:
        from notebooklm.paths import get_storage_path
        storage_path = get_storage_path()
    except Exception:
        from pathlib import Path
        storage_path = Path.home() / ".notebooklm" / "storage_state.json"

    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(json_str, encoding="utf-8")
