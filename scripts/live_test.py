"""Live end-to-end test harness for AuditPal against real NotebookLM.

Runs the exact NotebookService code paths so we can iterate fast without
the Streamlit UI. Requires NotebookLM credentials (NOTEBOOKLM_AUTH_JSON
env var, or a logged-in storage_state.json).

Usage:
    python scripts/live_test.py "notebook name substring"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.notebook import NotebookService  # noqa: E402


def main() -> None:
    wanted = sys.argv[1] if len(sys.argv) > 1 else ""
    svc = NotebookService()

    print("authenticated:", svc.is_authenticated())
    notebooks = svc.list_notebooks()
    print(f"notebooks ({len(notebooks)}):")
    for nb in notebooks:
        print("  -", nb["id"], nb["title"])

    nb = next(
        (n for n in notebooks if wanted.lower() in n["title"].lower()),
        notebooks[0] if notebooks else None,
    )
    if not nb:
        print("no notebook found")
        return
    print("\nusing notebook:", nb["title"], nb["id"])

    sources = svc.list_sources(nb["id"])
    print(f"sources: {len(sources)}")

    q1 = "Give a one-paragraph summary of the key accounting issue."
    a1, conv1, refs1 = svc.ask(nb["id"], q1)
    print("\n--- Q1 ---")
    print("conversation_id:", conv1)
    print("answer[:300]:", a1[:300])
    print("references:", len(refs1))

    history = [(q1, a1)]
    q2 = "Are you sure about your previous answer? Restate what I just asked."
    a2, conv2, refs2 = svc.ask(nb["id"], q2, conversation_id=conv1, history=history)
    print("\n--- Q2 (follow-up) ---")
    print("conversation_id:", conv2, "(same as Q1:", conv2 == conv1, ")")
    print("answer[:400]:", a2[:400])
    print(
        "\nCONTEXT RETAINED?",
        "looks NO" if "no preceding" in a2.lower() or "no previous" in a2.lower()
        else "looks YES",
    )

    if refs1:
        r = refs1[0]
        print("\n--- citation audit (ref 1) ---")
        print("source_id:", r["source_id"], "cited_text:", (r["cited_text"] or "")[:120])
        ft = svc.get_source_fulltext(nb["id"], r["source_id"], r["cited_text"])
        print("title:", ft["title"], "chars:", ft["char_count"])
        print("located contexts:", len(ft["contexts"]))
        if ft["contexts"]:
            print("context[:300]:", ft["contexts"][0]["context"][:300])


if __name__ == "__main__":
    main()
