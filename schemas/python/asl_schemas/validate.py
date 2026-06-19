"""Validate clip / sequence / gloss JSON files against the frozen contracts.

Used by CI to reject malformed dictionary clips (W0 acceptance) and by the
dictionary build pipeline (W6) to schema-validate every clip it writes.

Usage:
    python -m asl_schemas.validate clip   dictionary/*.json
    python -m asl_schemas.validate seq    out.json
    python -m asl_schemas.validate gloss  g.json
    python -m asl_schemas.validate auto   path/*.json   # infer by shape

Exit code is non-zero if any file fails, with a per-file error report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Type

from pydantic import BaseModel, ValidationError

from .models import GlossSequence, SMPLXClip, SMPLXSequence

_KIND_TO_MODEL: dict[str, Type[BaseModel]] = {
    "clip": SMPLXClip,
    "seq": SMPLXSequence,
    "sequence": SMPLXSequence,
    "gloss": GlossSequence,
}


def _infer_model(data: dict) -> Type[BaseModel]:
    """Best-effort model inference for `auto` mode."""
    if "clip_id" in data or data.get("kind") in ("lexical", "letter"):
        return SMPLXClip
    if "frames" in data and "model" in data:
        return SMPLXSequence
    if "gloss" in data and "english" in data:
        return GlossSequence
    raise ValueError("could not infer schema; pass an explicit kind")


def validate_file(path: Path, kind: str) -> list[str]:
    """Return a list of error strings (empty == valid)."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: not readable JSON: {exc}"]

    try:
        model = _infer_model(data) if kind == "auto" else _KIND_TO_MODEL[kind]
    except (KeyError, ValueError) as exc:
        return [f"{path}: {exc}"]

    try:
        model.model_validate(data)
    except ValidationError as exc:
        return [f"{path}: {err['loc']} -> {err['msg']}" for err in exc.errors()]
    return []


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2 or argv[0] not in {*_KIND_TO_MODEL, "auto"}:
        print(__doc__)
        return 2

    kind, paths = argv[0], [Path(p) for p in argv[1:]]
    all_errors: list[str] = []
    for path in paths:
        errors = validate_file(path, kind)
        status = "OK" if not errors else "FAIL"
        print(f"[{status}] {path}")
        all_errors.extend(errors)

    if all_errors:
        print(f"\n{len(all_errors)} error(s):", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"\nAll {len(paths)} file(s) valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
