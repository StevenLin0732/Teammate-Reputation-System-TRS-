import os
import sys
from pathlib import Path

# Avoid auto-seeding side effects during tool runs
os.environ.setdefault("TRS_DISABLE_AUTOSEED", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app import app  # noqa: E402


def main() -> None:
    c = app.test_client()

    page = c.get("/graph")
    print("/graph", page.status_code)

    r = c.get("/api/graph")
    print("status", r.status_code)
    j = r.get_json() or {}
    nodes = j.get("nodes") or []
    edges = j.get("edges") or []
    print("keys", sorted(j.keys()))
    print("nodes", len(nodes), "edges", len(edges))
    if nodes:
        print("sample node", nodes[0])
    if edges:
        print("sample edge", edges[0])


if __name__ == "__main__":
    main()
