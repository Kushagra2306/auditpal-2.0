"""Live end-to-end test harness for AuditPal against real NotebookLM.

Runs the exact NotebookService code paths so we can iterate fast without
the Streamlit UI. The pure market-test gating checks run with no
credentials; the live section requires NotebookLM credentials
(NOTEBOOKLM_AUTH_JSON env var, or a logged-in storage_state.json).

Usage:
    python scripts/live_test.py "notebook name substring"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Settings, resolve_pool_assignment  # noqa: E402
from services.notebook import NotebookService  # noqa: E402


def check_gating_logic() -> None:
    """Pure market-test gating assertions — no credentials needed."""
    print("=== gating logic (pure) ===")

    # Pool parsing: trims, drops empties, preserves order.
    s = Settings(demo_notebook_ids=" a , , b ,c ")
    assert s.get_demo_notebook_ids() == ["a", "b", "c"], s.get_demo_notebook_ids()

    # locked == lock_to_demo AND non-empty pool.
    assert (Settings(demo_notebook_ids="a", lock_to_demo=True)
            .get_demo_notebook_ids() and True) is True
    assert not Settings(demo_notebook_ids="", lock_to_demo=True).get_demo_notebook_ids()
    assert not Settings(demo_notebook_ids="a", lock_to_demo=False).lock_to_demo

    pool = ["nb1", "nb2", "nb3"]

    # Valid workspace code -> 1-indexed notebook.
    assert resolve_pool_assignment(pool, "1") == ("nb1", "code:1", None)
    assert resolve_pool_assignment(pool, "3") == ("nb3", "code:3", None)

    # Out-of-range / non-numeric / empty codes are rejected.
    assert resolve_pool_assignment(pool, "0")[2] is not None
    assert resolve_pool_assignment(pool, "4")[2] is not None
    assert resolve_pool_assignment(pool, "abc")[2] is not None
    assert resolve_pool_assignment(pool, "")[2] == "Please enter your workspace code."

    # Name fallback only when explicitly enabled.
    assert resolve_pool_assignment(pool, "", "Jane Doe")[0] is None
    a1 = resolve_pool_assignment(pool, "", "Jane Doe", allow_name_fallback=True)
    a2 = resolve_pool_assignment(pool, "", " jane doe ", allow_name_fallback=True)
    assert a1[0] in pool and a1[2] is None, a1
    assert a1[0] == a2[0], (a1, a2)  # case/space-insensitive & deterministic

    # Empty pool never raises (e.g. ZeroDivisionError on name hash).
    assert resolve_pool_assignment([], "1")[2] is not None
    assert resolve_pool_assignment([], "", "x", allow_name_fallback=True)[2] is not None

    print("  all pure gating assertions passed")


def check_gating_live(svc: NotebookService, notebooks: list) -> None:
    """Validate locked-mode assignment resolves to real, loadable notebooks."""
    print("\n=== gating logic (live) ===")
    if not notebooks:
        print("  no notebooks available; skipping live gating check")
        return

    pool = [n["id"] for n in notebooks[:3]]
    print(f"  synthetic demo pool ({len(pool)}):",
          [f'{i+1}->{n["title"]}' for i, n in enumerate(notebooks[:3])])

    for code in range(1, len(pool) + 1):
        assigned, tester_id, error = resolve_pool_assignment(pool, str(code))
        assert error is None and assigned == pool[code - 1], (code, assigned, error)
        srcs = svc.list_sources(assigned)
        print(f"  code {code} ({tester_id}) -> {assigned}: {len(srcs)} sources OK")

    # The pin: a locked tester selecting another notebook is a no-op.
    assigned_1 = resolve_pool_assignment(pool, "1")[0]
    other = next((i for i in pool if i != assigned_1), None)
    if other:
        print(f"  pin check: assigned={assigned_1}, attempted={other} "
              f"-> would be rejected by on_notebook_select (locked)")

    # Confirm a real ask works inside an assigned demo notebook.
    ans, conv, refs = svc.ask(pool[0], "In one sentence, what is this notebook about?")
    print(f"  ask in assigned notebook: conv={conv}, "
          f"answer[:120]={ans[:120]!r}, refs={len(refs)}")


def main() -> None:
    check_gating_logic()

    wanted = sys.argv[1] if len(sys.argv) > 1 else ""
    svc = NotebookService()

    print("\n=== core product (live) ===")
    print("authenticated:", svc.is_authenticated())
    if not svc.is_authenticated():
        print("\nNo NotebookLM credentials present — pure gating checks passed, "
              "live sections skipped. Set NOTEBOOKLM_AUTH_JSON and re-run.")
        return

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

    check_gating_live(svc, notebooks)


if __name__ == "__main__":
    main()
