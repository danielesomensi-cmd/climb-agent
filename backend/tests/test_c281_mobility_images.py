"""C281 — every Mobility stretch but one has an illustration, and the flow carries it.

The picture lives in the frontend's public folder; the catalog's `image` is its
public path and the generated flow copies it onto each step, so the player
needs no id → file map of its own. One-sided stretches also ship the mirrored
`<id>_l.webp` that the player shows on the left side's turn. The sleeper
stretch has none: the model kept drawing folded arms instead of the vertical
forearm, and the region silhouette misleads less than a wrong pose.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine.mobility import REGION_IDS, load_mobility_catalog

PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"
client = TestClient(app)
NO_PICTURE = {"stretch_sleeper"}


def _file(public_path: str) -> Path:
    return PUBLIC / public_path.lstrip("/")


def test_every_entry_points_to_its_shipped_picture():
    wrong = [
        e["id"] for e in load_mobility_catalog()
        if e["id"] not in NO_PICTURE
        and (e.get("image") != f"/exercises/stretch/{e['id']}.webp" or not _file(e["image"]).exists())
    ]
    assert wrong == []
    assert [e["id"] for e in load_mobility_catalog() if e["id"] in NO_PICTURE and e.get("image")] == []


def test_one_sided_entries_ship_the_mirrored_picture():
    missing = [
        e["id"] for e in load_mobility_catalog()
        if e["unilateral"] and e.get("image") and not _file(e["image"].replace(".webp", "_l.webp")).exists()
    ]
    assert missing == []


def test_flow_steps_carry_the_catalog_picture():
    images = {e["id"]: e.get("image") for e in load_mobility_catalog()}
    r = client.get(
        "/api/mobility/generate",
        params={"regions": ",".join(REGION_IDS), "minutes": 45, "pace": "standard", "rest": 10},
    )
    assert r.status_code == 200
    steps = r.json()["steps"]
    assert steps
    assert all(s["image"] == images[s["entry_id"]] for s in steps)
