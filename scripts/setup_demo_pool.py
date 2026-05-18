"""Create a pool of N identical demo notebooks for AuditPal market testing.

Each colleague is pinned (in-app, by workspace code) to one notebook from
this pool so their conversations never collide on the shared NotebookLM
account. This script builds the pool: it creates N notebooks and uploads the
same folder of (dummy) documents to each, then prints the comma-separated
notebook IDs to paste into the DEMO_NOTEBOOK_IDS secret/env var.

Requires NotebookLM credentials (NOTEBOOKLM_AUTH_JSON env var, or a
logged-in storage_state.json via `notebooklm login`).

Usage:
    python scripts/setup_demo_pool.py --docs ./demo_docs --count 20
    python scripts/setup_demo_pool.py --docs ./demo_docs --count 20 --prefix "AuditPal Demo"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.notebook import NotebookService  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the AuditPal demo notebook pool")
    ap.add_argument(
        "--docs", required=True,
        help="Folder of documents to upload to EVERY notebook",
    )
    ap.add_argument(
        "--count", type=int, default=20,
        help="Number of identical notebooks to create (default: 20)",
    )
    ap.add_argument(
        "--prefix", default="AuditPal Demo",
        help='Notebook title prefix (default: "AuditPal Demo")',
    )
    args = ap.parse_args()

    docs_dir = Path(args.docs).expanduser().resolve()
    files = (
        sorted(p for p in docs_dir.iterdir() if p.is_file())
        if docs_dir.is_dir()
        else []
    )
    if not files:
        print(f"No files found in {docs_dir}")
        sys.exit(1)

    svc = NotebookService()
    if not svc.is_authenticated():
        print(
            "Not authenticated. Run 'notebooklm login' locally, "
            "or set NOTEBOOKLM_AUTH_JSON."
        )
        sys.exit(1)

    print(
        f"Creating {args.count} notebook(s), uploading {len(files)} "
        f"file(s) to each…"
    )
    ids = []
    for i in range(1, args.count + 1):
        title = f"{args.prefix} {i}"
        nb = svc.create_notebook(title)
        nb_id = nb["id"]
        ok = 0
        for f in files:
            try:
                svc.add_file_source(nb_id, f)
                ok += 1
            except Exception as e:
                print(f"  [{title}] failed to add {f.name}: {e}")
        ids.append(nb_id)
        print(f"  created {title} -> {nb_id} ({ok}/{len(files)} sources)")

    print("\nDEMO_NOTEBOOK_IDS (paste into your secret/env var):")
    print(",".join(ids))
    print(
        "\nWorkspace codes: tell person 1 to enter '1', person 2 '2', … "
        f"up to '{len(ids)}' (order matches the list above)."
    )


if __name__ == "__main__":
    main()
