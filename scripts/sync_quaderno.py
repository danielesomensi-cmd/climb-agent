#!/usr/bin/env python3
"""Copy the athlete's quaderno into climb-agent's private storage (A321).

The quaderno (route drawings, per-second charts, beta) is built by Daniele's
climb-watch repo: every ``/quaderno`` run rewrites ``data/report/`` there, with a
``manifest.json`` (``climb-watch/report-manifest@1``) listing every file the
standalone page needs, with its size and sha256. climb-watch never writes to
climb-agent: this script, run on climb-agent's side, does the copy.

    python scripts/sync_quaderno.py                 # dry run: what would change
    python scripts/sync_quaderno.py --apply         # upload

Protocol (so a sync that stops half-way never serves a mix of two versions):
changed files first, ``manifest.json`` LAST, then the files the new manifest no
longer lists are deleted. The backend serves only what the stored manifest
lists. Running it twice does nothing the second time.

The user is ``--user-id`` or ``QUADERNO_USER_ID`` (environment or ``.env``);
the Supabase credentials come from the environment or ``.env`` as for
``athlete_context.py``. ``--local`` writes to the file backend instead (dev).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.engine.quaderno import (  # noqa: E402
    MANIFEST_PATH,
    ManifestError,
    content_type_for,
    parse_manifest,
    plan_sync,
)

DEFAULT_SRC = Path.home() / "Projects" / "climb-watch" / "data" / "report"

EXIT_OK = 0
EXIT_ERROR = 1


def _env_files() -> List[Path]:
    """``.env`` candidates: this checkout, then the primary worktree."""
    out = [REPO_ROOT / ".env"]
    try:
        common = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout.strip()
        if common:
            out.append(Path(common).parent / ".env")
    except Exception:
        pass
    return out


def env_value(name: str) -> Optional[str]:
    """``name`` from the environment, else from the first ``.env`` that has it."""
    if os.environ.get(name):
        return os.environ[name]
    for path in _env_files():
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            if k.strip() == name and v.strip():
                return v.strip().strip('"').strip("'")
    return None


def read_local_bundle(src: Path) -> Dict[str, Any]:
    """The local manifest (parsed and raw) and every file it lists, verified.

    Raises ManifestError when a listed file is missing or does not match its
    size / sha256 — the bundle is being rewritten, or was edited by hand.
    """
    raw = (src / MANIFEST_PATH).read_bytes()
    manifest = parse_manifest(raw)
    files: Dict[str, bytes] = {}
    for path, meta in manifest["files"].items():
        target = src / path
        if not target.is_file():
            raise ManifestError(f"{path} is listed in the manifest but missing")
        data = target.read_bytes()
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ManifestError(f"{path} does not match the manifest (size or sha256)")
        files[path] = data
    return {"raw": raw, "manifest": manifest, "files": files}


def sync(bundle: Dict[str, Any], user_id: str, store: Any, apply: bool) -> Dict[str, Any]:
    """Plan (and with ``apply``, run) the copy into ``store``.

    ``store`` exposes ``read_quaderno_file`` / ``write_quaderno_file`` /
    ``delete_quaderno_files`` (the storage module, or a fake in tests).
    """
    remote_raw = store.read_quaderno_file(user_id, MANIFEST_PATH)
    remote = None
    if remote_raw is not None:
        try:
            remote = parse_manifest(remote_raw)
        except ManifestError:
            remote = None  # unreadable: upload everything, the manifest last
    plan = plan_sync(bundle["manifest"], remote)
    manifest_changed = remote_raw != bundle["raw"]
    result = {
        "plan": plan,
        "manifest_changed": manifest_changed,
        "generated": bundle["manifest"]["generated"],
        "remote_generated": (remote or {}).get("generated"),
        "applied": False,
    }
    if not apply or (not plan["upload"] and not plan["delete"] and not manifest_changed):
        return result
    for path in plan["upload"]:
        store.write_quaderno_file(user_id, path, bundle["files"][path], content_type_for(path))
    store.write_quaderno_file(user_id, MANIFEST_PATH, bundle["raw"], content_type_for(MANIFEST_PATH))
    if plan["delete"]:
        store.delete_quaderno_files(user_id, plan["delete"])
    if store.read_quaderno_file(user_id, MANIFEST_PATH) != bundle["raw"]:
        raise RuntimeError("the stored manifest is not the one just uploaded")
    result["applied"] = True
    return result


def _print_result(result: Dict[str, Any], bundle: Dict[str, Any], apply: bool) -> None:
    plan = result["plan"]
    print(f"Quaderno locale:   {result['generated']} ({len(bundle['files'])} file)")
    print(f"Quaderno in app:   {result['remote_generated'] or '— (nessuno)'}")
    for path in plan["upload"]:
        print(f"  carica   {path} ({len(bundle['files'][path]):,} byte)")
    for path in plan["delete"]:
        print(f"  elimina  {path}")
    print(f"  invariati: {len(plan['unchanged'])}")
    if not plan["upload"] and not plan["delete"] and not result["manifest_changed"]:
        print("Già allineato: niente da fare.")
    elif result["applied"]:
        print("✅ Copiato. L'app mostra la nuova versione dalla prossima apertura.")
    elif not apply:
        print("Prova a secco: niente è stato scritto. Rilancia con --apply.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="climb-watch data/report folder")
    parser.add_argument("--user-id", help="climb-agent internal user id (default: QUADERNO_USER_ID)")
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--local", action="store_true", help="file backend instead of Supabase (dev)")
    args = parser.parse_args(argv)

    user_id = args.user_id or env_value("QUADERNO_USER_ID")
    if not user_id:
        print("Manca l'utente: --user-id o QUADERNO_USER_ID (env o .env).", file=sys.stderr)
        return EXIT_ERROR
    try:
        bundle = read_local_bundle(args.src)
    except FileNotFoundError:
        print(f"Nessun manifest in {args.src} — lancia prima /quaderno in climb-watch.", file=sys.stderr)
        return EXIT_ERROR
    except ManifestError as e:
        print(f"Quaderno locale non valido: {e}", file=sys.stderr)
        return EXIT_ERROR

    if not args.local:
        url, key = env_value("SUPABASE_URL"), env_value("SUPABASE_SERVICE_KEY")
        if not url or not key:
            print("SUPABASE_URL / SUPABASE_SERVICE_KEY non trovati (env o .env).", file=sys.stderr)
            return EXIT_ERROR
        os.environ["STORAGE_BACKEND"] = "supabase"
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"] = url, key
    else:
        os.environ["STORAGE_BACKEND"] = "file"
    from backend.engine import storage  # after the backend is chosen

    result = sync(bundle, user_id, storage, apply=args.apply)
    _print_result(result, bundle, args.apply)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
