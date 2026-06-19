"""In-memory stub dictionary for the §5 seed vocabulary.

Lets the /api/sign pipeline run end-to-end via LocalClipStore before W6's real
SMPL-X clips land in the GCS `dictionary` bucket. Poses are synthetic (a small
deterministic per-gloss wiggle of one body joint, rest-padded ends) — enough to
exercise lookup + blend and render *something*, not real ASL.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from asl_schemas import SMPLXClip, SMPLXFrame

# §5 seed vocabulary.
LEXICAL = [
    "HELLO", "HOW", "YOU", "TODAY", "MY", "NAME", "ME",
    "SIGN", "NOT", "BUT", "CAN", "HAPPY", "COMMUNICATE",
]
LETTERS = ["J", "A", "D", "E", "I"]

_FPS = 30.0
_N_FRAMES = 9  # rest -> peak -> rest


def _rest_frame() -> dict:
    return {
        "global_orient": [0.0, 0.0, 0.0],
        "body_pose": [0.0] * 63,
        "left_hand_pose": [0.0] * 45,
        "right_hand_pose": [0.0] * 45,
        "jaw_pose": [0.0, 0.0, 0.0],
        "leye_pose": [0.0, 0.0, 0.0],
        "reye_pose": [0.0, 0.0, 0.0],
        "expression": [0.0] * 10,
        "transl": [0.0, 0.0, 0.0],
    }


def _stub_clip(gloss: str, kind: str) -> SMPLXClip:
    # Deterministic per-gloss joint + axis so clips differ but stay valid.
    h = abs(hash(gloss))
    joint = h % 21               # which body joint (0..20)
    axis = h % 3                 # x/y/z
    peak = 0.6                   # radians, small

    # Smooth ramp rest -> peak -> rest (rest-padded ends per §4.6).
    ramp = np.sin(np.linspace(0.0, np.pi, _N_FRAMES)) * peak
    frames = []
    for amp in ramp:
        f = _rest_frame()
        f["body_pose"][joint * 3 + axis] = float(amp)
        frames.append(SMPLXFrame.model_validate(f))

    return SMPLXClip(
        clip_id=f"stub-{kind}-{gloss.lower()}",
        gloss=gloss,
        kind=kind,
        fps=_FPS,
        betas=[0.0] * 10,
        frames=frames,
        source={"extractor": "stub", "license": "POC-stub"},
    )


def build_stub_clips() -> list[SMPLXClip]:
    return (
        [_stub_clip(g, "lexical") for g in LEXICAL]
        + [_stub_clip(l, "letter") for l in LETTERS]
    )


def write_stub_dictionary(directory: str | Path) -> Path:
    """Write stub clips as one JSON each so LocalClipStore can read them."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    for clip in build_stub_clips():
        (out / f"{clip.clip_id}.json").write_text(clip.model_dump_json())
    return out
