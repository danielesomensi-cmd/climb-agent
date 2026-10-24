"""A321 — the athlete's quaderno (route report) hosted read-only in the app.

Covers the pure half (paths, manifest, sync plan, signed link), the file
storage backend, the two endpoints (what is served, to whom, with which
headers) and the sync script's upload protocol (manifest last, then deletes).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine import quaderno as q
from backend.engine import storage_file

client = TestClient(app)

SECRET = "test-secret-a321"
USER_A = "3f0c9a52-6d1e-4b7a-9c3e-1a2b3c4d5e6f"
USER_B = "8d4e2f10-7a6b-4c5d-8e9f-0a1b2c3d4e5f"

_spec = importlib.util.spec_from_file_location(
    "sync_quaderno", Path(__file__).resolve().parents[2] / "scripts" / "sync_quaderno.py"
)
sync_quaderno = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_quaderno)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _bundle_files(generated: str = "2026-10-24T21:40:35+02:00") -> dict:
    days = {"schema": "climb-watch/report-index@1", "generated": generated,
            "days": [{"date": "2026-10-11"}, {"date": "2026-10-17"}, {"date": "bad"}]}
    return {
        "standalone.html": b"<!doctype html><title>Quaderno</title>",
        "data/days.json": json.dumps(days).encode(),
        "data/day-2026-10-17.json": b'{"date": "2026-10-17"}',
        "img/isatis-wall.webp": b"RIFF\x00\x00WEBP",
    }


def _manifest_bytes(files: dict, generated: str = "2026-10-24T21:40:35+02:00") -> bytes:
    entries = [
        {"path": p, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        for p, b in sorted(files.items())
    ]
    return json.dumps({"schema": q.MANIFEST_SCHEMA, "generated": generated, "files": entries}).encode()


def _store_bundle(user_id: str, files: dict) -> None:
    for path, data in files.items():
        storage_file.write_quaderno_file(user_id, path, data, q.content_type_for(path))
    storage_file.write_quaderno_file(user_id, q.MANIFEST_PATH, _manifest_bytes(files), "application/json")


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("QUADERNO_LINK_SECRET", SECRET)
    return SECRET


def _get(path: str, user_id: str = USER_A):
    return client.get(path, headers={"X-User-ID": user_id})


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "standalone.html", "manifest.json", "data/days.json",
    "data/day-2026-10-17.json", "img/isatis-wall.webp", "img/wall.JPG",
])
def test_safe_paths(path):
    assert q.is_safe_path(path)


@pytest.mark.parametrize("path", [
    "", None, "/etc/passwd.json", "../x.json", "data/../manifest.json", "data/./x.json",
    "data//x.json", "data\\x.json", ".env", "data/.hidden.json", "x.exe", "x.svg",
    "data/x", "a b.json", "x" * 201 + ".json",
])
def test_unsafe_paths(path):
    assert not q.is_safe_path(path)


def test_content_types():
    assert q.content_type_for("standalone.html") == "text/html; charset=utf-8"
    assert q.content_type_for("data/days.json") == "application/json"
    assert q.content_type_for("img/a.webp") == "image/webp"
    assert q.content_type_for("x.svg") is None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def test_parse_manifest_ok():
    m = q.parse_manifest(_manifest_bytes(_bundle_files()))
    assert m["generated"] == "2026-10-24T21:40:35+02:00"
    assert set(m["files"]) == set(_bundle_files())
    assert m["files"]["standalone.html"]["bytes"] == len(_bundle_files()["standalone.html"])


def _raw(**over) -> bytes:
    base = json.loads(_manifest_bytes(_bundle_files()))
    base.update(over)
    return json.dumps(base).encode()


@pytest.mark.parametrize("raw", [
    b"not json",
    _raw(schema="climb-watch/report-manifest@2"),
    _raw(generated=""),
    _raw(files=[]),
    _raw(files=[{"path": "data/days.json", "bytes": 1, "sha256": "0" * 64}]),  # no page
    _raw(files=[{"path": "standalone.html", "bytes": 1, "sha256": "zz"}]),
    _raw(files=[{"path": "standalone.html", "bytes": -1, "sha256": "0" * 64}]),
    _raw(files=[{"path": "../standalone.html", "bytes": 1, "sha256": "0" * 64}]),
    _raw(files=[{"path": "manifest.json", "bytes": 1, "sha256": "0" * 64},
                {"path": "standalone.html", "bytes": 1, "sha256": "0" * 64}]),
    _raw(files=[{"path": "standalone.html", "bytes": 1, "sha256": "0" * 64},
                {"path": "standalone.html", "bytes": 1, "sha256": "0" * 64}]),
])
def test_parse_manifest_rejects(raw):
    with pytest.raises(q.ManifestError):
        q.parse_manifest(raw)


def test_plan_sync():
    files = _bundle_files()
    local = q.parse_manifest(_manifest_bytes(files))
    assert q.plan_sync(local, None) == {"upload": sorted(files), "delete": [], "unchanged": []}
    assert q.plan_sync(local, local)["upload"] == []

    changed = dict(files, **{"data/days.json": b"{}", "data/day-2026-10-11.json": b"{}"})
    del changed["img/isatis-wall.webp"]
    plan = q.plan_sync(q.parse_manifest(_manifest_bytes(changed)), local)
    assert plan["upload"] == ["data/day-2026-10-11.json", "data/days.json"]
    assert plan["delete"] == ["img/isatis-wall.webp"]
    assert plan["unchanged"] == ["data/day-2026-10-17.json", "standalone.html"]


def test_days_from_index():
    assert q.days_from_index(_bundle_files()["data/days.json"]) == ["2026-10-17", "2026-10-11"]
    assert q.days_from_index(b"nope") == []
    assert q.days_from_index(b'{"days": "x"}') == []


# ---------------------------------------------------------------------------
# Signed link
# ---------------------------------------------------------------------------

def test_link_round_trip_and_expiry():
    token = q.sign_link(USER_A, SECRET, now=1000, ttl=60)
    assert q.link_expiry(token) == 1060
    assert q.verify_link(token, SECRET, now=1060) == USER_A
    assert q.verify_link(token, SECRET, now=1061) is None


def test_link_rejects_tampering():
    token = q.sign_link(USER_A, SECRET, now=1000)
    uid, exp, sig = token.split(".")
    other_uid = q.sign_link(USER_B, SECRET, now=1000).split(".")[0]
    assert q.verify_link(f"{other_uid}.{exp}.{sig}", SECRET, now=1000) is None
    assert q.verify_link(f"{uid}.{int(exp) + 999}.{sig}", SECRET, now=1000) is None
    assert q.verify_link(token, "another-secret", now=1000) is None
    for junk in ("", "a.b", "a.b.c.d", "...", token + "x"):
        assert q.verify_link(junk, SECRET, now=1000) is None
    assert q.verify_link(token, "", now=1000) is None


def test_link_is_path_safe():
    token = q.sign_link("7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e", SECRET, now=1_800_000_000)
    assert all(c.isalnum() or c in "-_." for c in token)


# ---------------------------------------------------------------------------
# File storage backend
# ---------------------------------------------------------------------------

def test_file_storage_round_trip():
    assert storage_file.read_quaderno_file(USER_A, "data/days.json") is None
    storage_file.write_quaderno_file(USER_A, "data/days.json", b"{}", "application/json")
    assert storage_file.read_quaderno_file(USER_A, "data/days.json") == b"{}"
    assert storage_file.read_quaderno_file(USER_B, "data/days.json") is None
    storage_file.delete_quaderno_files(USER_A, ["data/days.json", "data/missing.json"])
    assert storage_file.read_quaderno_file(USER_A, "data/days.json") is None


@pytest.mark.parametrize("user_id,path", [
    (USER_A, "../escape.json"), (USER_A, ".env"), (None, "data/days.json"),
    ("..", "data/days.json"), ("a/b", "data/days.json"),
])
def test_file_storage_refuses_unsafe(user_id, path):
    with pytest.raises(ValueError):
        storage_file.write_quaderno_file(user_id, path, b"x", "application/json")


def test_account_deletion_removes_the_quaderno():
    _store_bundle(USER_A, _bundle_files())
    storage_file.delete_user_data(USER_A)
    assert storage_file.read_quaderno_file(USER_A, q.MANIFEST_PATH) is None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def test_off_without_secret(monkeypatch):
    monkeypatch.delenv("QUADERNO_LINK_SECRET", raising=False)
    _store_bundle(USER_A, _bundle_files())
    assert _get("/api/quaderno").json() == {"available": False}


def test_unavailable_without_a_bundle(secret):
    assert _get("/api/quaderno", USER_B).json() == {"available": False}


def test_unavailable_with_a_broken_manifest(secret):
    storage_file.write_quaderno_file(USER_A, q.MANIFEST_PATH, b"{broken", "application/json")
    assert _get("/api/quaderno").json() == {"available": False}


def test_info_and_page(secret):
    _store_bundle(USER_A, _bundle_files())
    info = _get("/api/quaderno").json()
    assert info["available"] is True
    assert info["days"] == ["2026-10-17", "2026-10-11"]
    assert info["generated"] == "2026-10-24T21:40:35+02:00"
    assert info["page_path"].startswith("/api/quaderno/v/")
    assert info["page_path"].endswith("/standalone.html")

    r = client.get(info["page_path"])  # no bearer: the iframe cannot send one
    assert r.status_code == 200
    assert r.content == _bundle_files()["standalone.html"]
    assert r.headers["content-type"] == "text/html; charset=utf-8"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["access-control-allow-origin"] == "*"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-content-type-options"] == "nosniff"
    csp = r.headers["content-security-policy"]
    assert csp.startswith("sandbox allow-scripts;")
    assert "allow-same-origin" not in csp
    assert "frame-ancestors https://climbagent.app" in csp
    assert "default-src 'none'" in csp

    base = info["page_path"].rsplit("/", 1)[0]
    data = client.get(f"{base}/data/days.json")
    assert data.status_code == 200
    assert data.headers["content-type"] == "application/json"
    assert data.headers["access-control-allow-origin"] == "*"
    img = client.get(f"{base}/img/isatis-wall.webp")
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp"


def test_serves_only_what_the_manifest_lists(secret):
    files = _bundle_files()
    _store_bundle(USER_A, files)
    storage_file.write_quaderno_file(USER_A, "data/stray.json", b"{}", "application/json")
    base = _get("/api/quaderno").json()["page_path"].rsplit("/", 1)[0]
    assert client.get(f"{base}/data/stray.json").status_code == 404
    assert client.get(f"{base}/manifest.json").status_code == 404
    assert client.get(f"{base}/data/nothing.json").status_code == 404
    assert client.get(f"{base}/.env").status_code == 404


def test_bad_or_expired_link(secret, monkeypatch):
    _store_bundle(USER_A, _bundle_files())
    page = _get("/api/quaderno").json()["page_path"]
    token = page.split("/")[4]
    assert client.get(page.replace(token, token[:-2] + "xx")).status_code == 403
    assert client.get("/api/quaderno/v/garbage/standalone.html").status_code == 403

    import backend.api.routers.quaderno as router_mod
    real_time = router_mod.time.time
    monkeypatch.setattr(router_mod.time, "time", lambda: real_time() + q.LINK_TTL_SECONDS + 5)
    assert client.get(page).status_code == 403


def test_link_without_secret_is_refused(secret, monkeypatch):
    _store_bundle(USER_A, _bundle_files())
    page = _get("/api/quaderno").json()["page_path"]
    monkeypatch.delenv("QUADERNO_LINK_SECRET")
    assert client.get(page).status_code == 403


def test_a_link_only_reads_its_own_user(secret):
    _store_bundle(USER_A, _bundle_files())
    other = dict(_bundle_files(), **{"standalone.html": b"<!doctype html><title>B</title>"})
    _store_bundle(USER_B, other)
    page_b = _get("/api/quaderno", USER_B).json()["page_path"]
    assert client.get(page_b).content == other["standalone.html"]
    page_a = _get("/api/quaderno", USER_A).json()["page_path"]
    assert client.get(page_a).content == _bundle_files()["standalone.html"]


# ---------------------------------------------------------------------------
# Sync script
# ---------------------------------------------------------------------------

class FakeStore:
    def __init__(self):
        self.files: dict = {}
        self.log: list = []

    def read_quaderno_file(self, user_id, path):
        return self.files.get((user_id, path))

    def write_quaderno_file(self, user_id, path, data, content_type):
        assert content_type
        self.files[(user_id, path)] = data
        self.log.append(("write", path))

    def delete_quaderno_files(self, user_id, paths):
        for p in paths:
            self.files.pop((user_id, p), None)
            self.log.append(("delete", p))


def _write_local(src: Path, files: dict, generated: str = "2026-10-24T21:40:35+02:00") -> None:
    for path, data in files.items():
        (src / path).parent.mkdir(parents=True, exist_ok=True)
        (src / path).write_bytes(data)
    (src / q.MANIFEST_PATH).write_bytes(_manifest_bytes(files, generated))


def test_sync_dry_run_writes_nothing(tmp_path):
    _write_local(tmp_path, _bundle_files())
    store = FakeStore()
    result = sync_quaderno.sync(sync_quaderno.read_local_bundle(tmp_path), USER_A, store, apply=False)
    assert result["plan"]["upload"] == sorted(_bundle_files())
    assert result["applied"] is False and store.log == []


def test_sync_uploads_manifest_last_then_deletes(tmp_path):
    files = _bundle_files()
    _write_local(tmp_path, files)
    store = FakeStore()
    sync_quaderno.sync(sync_quaderno.read_local_bundle(tmp_path), USER_A, store, apply=True)
    assert store.log[-1] == ("write", q.MANIFEST_PATH)
    assert {p for _, p in store.log} == set(files) | {q.MANIFEST_PATH}

    # Second run: nothing to do.
    store.log.clear()
    result = sync_quaderno.sync(sync_quaderno.read_local_bundle(tmp_path), USER_A, store, apply=True)
    assert store.log == [] and result["applied"] is False

    # A new /quaderno run: one day changed, the photo gone.
    newer = dict(files, **{"data/days.json": b'{"days": []}'})
    del newer["img/isatis-wall.webp"]
    (tmp_path / "img" / "isatis-wall.webp").unlink()
    _write_local(tmp_path, newer, generated="2026-10-25T10:00:00+02:00")
    sync_quaderno.sync(sync_quaderno.read_local_bundle(tmp_path), USER_A, store, apply=True)
    assert store.log == [
        ("write", "data/days.json"),
        ("write", q.MANIFEST_PATH),
        ("delete", "img/isatis-wall.webp"),
    ]


def test_sync_refuses_a_bundle_that_does_not_match_its_manifest(tmp_path):
    _write_local(tmp_path, _bundle_files())
    (tmp_path / "data" / "days.json").write_bytes(b"rewritten mid-run")
    with pytest.raises(q.ManifestError):
        sync_quaderno.read_local_bundle(tmp_path)
    (tmp_path / "data" / "days.json").unlink()
    with pytest.raises(q.ManifestError):
        sync_quaderno.read_local_bundle(tmp_path)


def test_sync_main_local_backend(tmp_path, capsys):
    src = tmp_path / "report"
    _write_local(src, _bundle_files())
    rc = sync_quaderno.main(["--src", str(src), "--user-id", USER_A, "--local", "--apply"])
    assert rc == 0
    assert storage_file.read_quaderno_file(USER_A, "standalone.html") == _bundle_files()["standalone.html"]
    assert sync_quaderno.main(["--src", str(tmp_path / "missing"), "--user-id", USER_A, "--local"]) == 1
