"""D64: RED-S awareness guardrails.

The engine must NEVER suggest weight loss, calorie restriction, or body
composition changes. RED-S (Relative Energy Deficiency in Sport) is
prevalent in climbing — the app must not contribute to it.

These tests scan the entire codebase for banned language and verify
structural safety (no body composition axis, no body fat metrics).
"""

import os
import glob

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BANNED_PHRASES = [
    "weight loss",
    "lose weight",
    "fat burn",
    "calorie deficit",
    "body fat",
    "body composition score",
    "slim down",
    "lean out",
    "cut weight",
    "make weight",
]

# Files that legitimately reference banned phrases (this test file, archived docs)
ALLOWED_FILES = {
    "test_reds_guardrails.py",
}


def _scan_files():
    """Yield (filepath, line_num, line) for all source files."""
    patterns = [
        os.path.join(REPO_ROOT, "backend", "**", "*.py"),
        os.path.join(REPO_ROOT, "backend", "**", "*.json"),
        os.path.join(REPO_ROOT, "frontend", "src", "**", "*.ts"),
        os.path.join(REPO_ROOT, "frontend", "src", "**", "*.tsx"),
    ]
    for pattern in patterns:
        for fpath in glob.glob(pattern, recursive=True):
            if "__pycache__" in fpath or "_archive" in fpath or "node_modules" in fpath:
                continue
            basename = os.path.basename(fpath)
            if basename in ALLOWED_FILES:
                continue
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        yield fpath, i, line.lower()
            except OSError:
                continue


def test_no_weight_loss_language_in_codebase():
    """Banned weight-loss/body-composition language must not appear anywhere."""
    violations = []
    for fpath, line_num, line in _scan_files():
        for phrase in BANNED_PHRASES:
            if phrase in line:
                rel = os.path.relpath(fpath, REPO_ROOT)
                violations.append(f"  {rel}:{line_num}: '{phrase}' in: {line.strip()[:120]}")
    assert violations == [], (
        "RED-S guardrail violations found:\n" + "\n".join(violations)
    )


def test_assessment_has_exactly_5_axes():
    """D01: body_composition axis must be removed. Assessment has exactly 5 axes."""
    from backend.engine.assessment_v1 import compute_assessment_profile

    profile = compute_assessment_profile(
        assessment={
            "body": {"weight_kg": 75, "height_cm": 178, "age": 30},
            "experience": {"climbing_years": 5, "training_years": 3},
            "grades": {"lead_max_rp": "7a", "boulder_max_rp": "6c"},
            "tests": {},
            "self_eval": {},
        },
        goal={"target_grade": "7c+", "current_grade": "7a"},
    )
    assert set(profile.keys()) == {
        "finger_strength",
        "pulling_strength",
        "power_endurance",
        "technique",
        "endurance",
    }, f"Expected exactly 5 axes, got: {set(profile.keys())}"
    assert "body_composition" not in profile


def test_body_fat_pct_not_in_engine():
    """body_fat_pct must not be read or used by any engine module."""
    engine_dir = os.path.join(REPO_ROOT, "backend", "engine")
    violations = []
    for fpath in glob.glob(os.path.join(engine_dir, "**", "*.py"), recursive=True):
        if "__pycache__" in fpath:
            continue
        with open(fpath) as f:
            for i, line in enumerate(f, 1):
                if "body_fat" in line.lower() and not line.strip().startswith("#"):
                    rel = os.path.relpath(fpath, REPO_ROOT)
                    violations.append(f"  {rel}:{i}: {line.strip()[:120]}")
    assert violations == [], (
        "body_fat_pct found in engine code:\n" + "\n".join(violations)
    )
