import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ABS = (REPO_ROOT / "backend" / "data" / "schemas" / "session_log_entry.v1.json").resolve()

def run_cli(entry: dict, tmpdir: Path):
    tmpdir.mkdir(parents=True, exist_ok=True)
    entry_path = tmpdir / "entry.json"
    entry_path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")

    main_log = "main.jsonl"
    rejected_log = "rejected.jsonl"
    bak_dir = "_bak"

    cmd = [
        sys.executable,
        str(REPO_ROOT / "_archive" / "scripts_legacy" / "scripts" / "append_session_log.py"),
        "--repo_root", str(tmpdir),
        "--log_template_path", str(entry_path),
        "--log_path", main_log,
        "--rejected_log_path", rejected_log,
        "--bak_dir", bak_dir,
        "--schema_path", str(SCHEMA_ABS),
        "--user_state_path", str(tmpdir / "no_user_state.json"),
    ]
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return p, tmpdir / main_log, tmpdir / rejected_log, tmpdir / bak_dir / "legacy_session_logs.jsonl"

def load_fixture(name: str) -> dict:
    p = REPO_ROOT / "backend" / "tests" / "fixtures" / name
    return json.loads(p.read_text(encoding="utf-8"))

def test_valid_v1_goes_to_main(tmp_path):
    entry = load_fixture("log_good.json")
    p, main_log, rejected_log, legacy_log = run_cli(entry, tmp_path)
    assert p.returncode == 0
    assert main_log.exists()
    assert not rejected_log.exists()
    assert not legacy_log.exists()

def test_invalid_v1_goes_to_rejected(tmp_path):
    entry = load_fixture("log_invalid_deep.json")
    p, main_log, rejected_log, legacy_log = run_cli(entry, tmp_path)
    assert p.returncode == 2
    assert rejected_log.exists()
    assert not legacy_log.exists()

def test_missing_schema_version_goes_to_legacy(tmp_path):
    entry = load_fixture("log_good.json")
    entry.pop("schema_version", None)
    p, main_log, rejected_log, legacy_log = run_cli(entry, tmp_path)
    assert p.returncode == 3
    assert legacy_log.exists()
    assert not main_log.exists()
