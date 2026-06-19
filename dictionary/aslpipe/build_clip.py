"""Assemble frames into a §3.2 SMPLXClip and schema-validate before writing.

Validation goes through the frozen pydantic model (asl_schemas.SMPLXClip), so a
clip with a 44-dim hand pose, wrong fps, or an unknown field is rejected here —
the same check CI runs (W0). Nothing reaches the dictionary bucket unvalidated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .posekit import BETAS_DIM, Frame

# Make the schemas package importable whether or not it is pip-installed.
_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas" / "python"
if _SCHEMAS.exists() and str(_SCHEMAS) not in sys.path:
    sys.path.insert(0, str(_SCHEMAS))

from asl_schemas import SMPLXClip  # noqa: E402  (after sys.path shim)


def build_clip(
    *,
    clip_id: str,
    gloss: str,
    kind: str,
    fps: float,
    frames: list[Frame],
    betas: list[float] | None = None,
    video_url: str | None = None,
    license: str | None = None,
    extractor: str | None = None,
) -> dict:
    """Build a validated SMPLXClip dict. Raises pydantic ValidationError on any
    contract violation."""
    betas = betas if betas is not None else [0.0] * BETAS_DIM
    payload = {
        "clip_id": clip_id,
        "gloss": gloss,
        "kind": kind,
        "fps": fps,
        "betas": betas,
        "frames": [f.to_dict() for f in frames],
        "source": {"video_url": video_url, "license": license, "extractor": extractor},
    }
    # round-trip through the model: validates, and normalises optional fields
    return SMPLXClip.model_validate(payload).model_dump()


def write_clip(clip: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{clip['clip_id']}.json"
    path.write_text(json.dumps(clip, separators=(",", ":")))
    return path
