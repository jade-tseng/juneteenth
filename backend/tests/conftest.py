"""Stub-clip builders for W3/W4 tests (no real dictionary needed yet)."""

from __future__ import annotations

from asl_schemas import SMPLXClip, SMPLXFrame


def frame(global_orient=(0.0, 0.0, 0.0), body0=(0.0, 0.0, 0.0)) -> dict:
    """A frame with all-rest pose except global_orient and the first body joint."""
    body = [0.0] * 63
    body[0:3] = list(body0)
    return {
        "global_orient": list(global_orient),
        "body_pose": body,
        "left_hand_pose": [0.0] * 45,
        "right_hand_pose": [0.0] * 45,
        "jaw_pose": [0.0, 0.0, 0.0],
        "leye_pose": [0.0, 0.0, 0.0],
        "reye_pose": [0.0, 0.0, 0.0],
        "expression": [0.0] * 10,
        "transl": [0.0, 0.0, 0.0],
    }


def clip(gloss: str, kind: str = "lexical", frames: list[dict] | None = None,
         fps: float = 30.0) -> SMPLXClip:
    frames = frames or [frame(), frame()]
    return SMPLXClip(
        clip_id=f"{gloss.lower()}-{kind}",
        gloss=gloss,
        kind=kind,
        fps=fps,
        betas=[0.0] * 10,
        frames=[SMPLXFrame.model_validate(f) for f in frames],
    )
