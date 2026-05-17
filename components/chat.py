"""Chat interface component for AuditPal."""

import html
import re
import streamlit as st
from typing import List, Callable
from datetime import datetime

from config import PROMPT_TEMPLATES

_CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

_CITATION_CSS = """
<style>
.cite-marker {
    position: relative;
    display: inline-block;
    color: #0066cc;
    font-weight: 700;
    background: #e8f0fe;
    padding: 1px 6px;
    border-radius: 4px;
    margin: 0 2px;
    font-size: 0.78em;
    cursor: help;
    line-height: 1.2;
}
.cite-marker:hover { background: #d4e3fc; }
.cite-tooltip {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    width: max-content;
    max-width: 520px;
    min-width: 260px;
    max-height: 340px;
    overflow-y: auto;
    background: #1f1f1f;
    color: #f1f3f4;
    padding: 12px 14px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 400;
    text-align: left;
    z-index: 999999;
    box-shadow: 0 6px 20px rgba(0,0,0,0.45);
    white-space: normal;
    line-height: 1.5;
    transition: opacity 0.12s, visibility 0.12s;
    user-select: text;
    cursor: text;
}
.cite-tooltip::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    height: 10px;
}
.cite-marker:hover .cite-tooltip,
.cite-tooltip:hover {
    visibility: visible;
    opacity: 1;
}
.cite-tt-title {
    display: block;
    color: #8ab4f8;
    font-weight: 600;
    font-size: 11.5px;
    margin-bottom: 5px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.cite-tt-text { display: block; color: #e8eaed; font-style: italic; }
.cite-tt-empty { display: block; color: #9aa0a6; font-style: italic; }
</style>
"""


def _render_assistant_message(content: str, references: List[dict]):
    """Render an assistant message with inline hover-tooltip citations."""
    if not references:
        st.markdown(content)
        return

    refs_by_num = {
        r["citation_number"]: r for r in references if r.get("citation_number")
    }

    def _badge(n: int) -> str:
        ref = refs_by_num.get(n)
        if not ref:
            return f"[{n}]"
        title = html.escape(ref.get("source_title") or "Source")
        excerpt = ref.get("expanded_text") or ref.get("cited_text") or ""
        if excerpt:
            body_html = html.escape(excerpt[:1500]).replace("\n", "<br>")
            body = f'<span class="cite-tt-text">{body_html}</span>'
        else:
            body = '<span class="cite-tt-empty">(no excerpt extracted)</span>'
        return (
            f'<span class="cite-marker">[{n}]'
            f'<span class="cite-tooltip">'
            f'<span class="cite-tt-title">{title}</span>{body}'
            f'</span></span>'
        )

    def _replace(match):
        nums = [int(n.strip()) for n in match.group(1).split(",")]
        return "".join(_badge(n) for n in nums)

    enhanced = _CITATION_PATTERN.sub(_replace, content)
    st.markdown(enhanced, unsafe_allow_html=True)


def _highlight(context: str, cited_text: str | None) -> str:
    """Escape a context block and visually mark the cited passage in it."""
    esc = html.escape(context)
    if cited_text:
        full = html.escape(cited_text)
        prefix = html.escape(cited_text[:40])
        if full and full in esc:
            esc = esc.replace(full, f"<mark>{full}</mark>", 1)
        elif prefix and prefix in esc:
            esc = esc.replace(prefix, f"<mark>{prefix}</mark>", 1)
    return (
        '<div style="white-space:pre-wrap;line-height:1.55;font-size:13.5px;'
        'background:#fafafa;padding:12px;border-radius:6px;'
        f'border:1px solid #e6e6e6">{esc}</div>'
    )


@st.dialog("📄 Source — citation audit", width="large")
def _source_dialog(req: dict, on_view_source: Callable):
    """Modal showing the cited passage highlighted within the full source."""
    with st.spinner("Loading source…"):
        try:
            data = on_view_source(req["source_id"], req.get("cited_text"))
        except Exception as e:
            st.error(f"Could not load source: {e}")
            return

    st.markdown(f"**{data.get('title') or 'Source'}**")
    st.caption(
        f"Citation [{req['n']}] · {data.get('char_count', 0):,} characters indexed"
    )

    contexts = data.get("contexts") or []
    if contexts:
        st.markdown("**Cited passage in context:**")
        for i, c in enumerate(contexts):
            st.markdown(_highlight(c["context"], req.get("cited_text")),
                        unsafe_allow_html=True)
            if i < len(contexts) - 1:
                st.divider()
    elif req.get("cited_text"):
        st.info(
            "Couldn't locate the exact passage in the indexed text "
            "(NotebookLM may have reformatted or truncated it). "
            "The full source is below."
        )

    with st.expander("📄 Full source text", expanded=not contexts):
        st.text_area(
            "Full text",
            data.get("content") or "(no text content available)",
            height=420,
            disabled=True,
            label_visibility="collapsed",
            key=f"ft_{req['source_id']}_{req['n']}",
        )


def _render_citations(references: List[dict], on_view_source: Callable, key_prefix: str):
    """Render an auditable list of citations with a source viewer per entry."""
    refs = [r for r in references if r.get("source_id")]
    if not refs:
        return

    with st.expander(f"📚 Sources & citations ({len(refs)}) — click to audit"):
        for r in refs:
            n = r.get("citation_number")
            title = r.get("source_title") or "Source"
            cited = r.get("expanded_text") or r.get("cited_text") or ""

            st.markdown(f"**[{n}] {title}**")
            if cited:
                st.markdown(f"> {cited}")
            else:
                st.caption("_(no excerpt returned by NotebookLM for this citation)_")

            if st.button(
                f"🔍 View source [{n}]",
                key=f"{key_prefix}_vs_{n}_{r.get('source_id')}",
            ):
                _source_dialog(
                    {
                        "source_id": r["source_id"],
                        "cited_text": cited or None,
                        "title": title,
                        "n": n,
                    },
                    on_view_source,
                )
            st.divider()


def render_chat(
    messages: List[dict],
    on_send: Callable[[str], str],
    on_clear: Callable,
    on_export: Callable[[str], None],
    on_view_source: Callable[[str, str], dict],
    disabled: bool = False
):
    """Render the chat interface."""

    st.markdown(_CITATION_CSS, unsafe_allow_html=True)

    # Header with actions
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown("## 💬 Chat")
    with col2:
        if st.button("🗑️ Clear", use_container_width=True, disabled=disabled):
            on_clear()
            st.rerun()
    with col3:
        export_format = st.selectbox(
            "Export",
            options=["", "Markdown", "PDF"],
            label_visibility="collapsed",
            disabled=disabled or not messages
        )
        if export_format:
            on_export(export_format.lower())
    
    if disabled:
        st.warning("⚠️ Add sources to start chatting")
        return
    
    # Quick templates
    with st.expander("🎯 Quick Templates", expanded=False):
        cols = st.columns(4)
        templates_list = list(PROMPT_TEMPLATES.items())[:8]  # Show first 8
        
        for idx, (key, template) in enumerate(templates_list):
            with cols[idx % 4]:
                if st.button(
                    template["name"].split(" ", 1)[0],  # Just emoji
                    key=f"quick_{key}",
                    help=template["name"],
                    use_container_width=True
                ):
                    st.session_state["pending_message"] = template["prompt"]
                    st.rerun()
    
    # Chat messages container
    chat_container = st.container()

    with chat_container:
        if not messages:
            st.info("👋 Ask a question about your documents!")
        else:
            for idx, msg in enumerate(messages):
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        _render_assistant_message(
                            msg["content"], msg.get("references", [])
                        )
                        _render_citations(
                            msg.get("references", []), on_view_source, f"m{idx}"
                        )
                        if st.button("📋 Copy", key=f"copy_{idx}"):
                            st.toast("Copied to clipboard!")
                    else:
                        st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about your documents...", disabled=disabled):
        _handle_message(prompt, messages, on_send, on_view_source, chat_container)

    # Handle pending message from template
    if "pending_message" in st.session_state:
        prompt = st.session_state.pop("pending_message")
        _handle_message(prompt, messages, on_send, on_view_source, chat_container)


def _handle_message(
    prompt: str,
    messages: List[dict],
    on_send: Callable,
    on_view_source: Callable,
    container,
):
    """Handle sending a message and getting response."""
    
    # Add user message
    messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().isoformat()
    })
    
    with container:
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = on_send(prompt)
                    if isinstance(response, dict):
                        answer = response.get("answer", "")
                        references = response.get("references", [])
                    else:
                        answer = response
                        references = []

                    _render_assistant_message(answer, references)
                    _render_citations(
                        references, on_view_source, f"live{len(messages)}"
                    )

                    messages.append({
                        "role": "assistant",
                        "content": answer,
                        "references": references,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    messages.append({
                        "role": "assistant",
                        "content": error_msg,
                        "references": [],
                        "timestamp": datetime.now().isoformat()
                    })
