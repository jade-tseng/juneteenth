"""Make `aslpipe` and the frozen `asl_schemas` importable from the test dir,
regardless of install state (mirrors build.py / build_clip.py path shims)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # dictionary/
SCHEMAS = ROOT.parent / "schemas" / "python"     # schemas/python

for p in (ROOT, SCHEMAS):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
