import os
import sys
from pathlib import Path

# B165d: disable rate limiting during tests
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

# Ensure repo root is importable so `import backend...` works in pytest
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
