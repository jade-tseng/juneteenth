"""Frozen data contracts for the Voice-to-ASL Signing Avatar POC.

These pydantic models are the single source of truth for §3 of CLAUDE.md.
JSON Schema (schemas/json/) and the TypeScript types (schemas/ts/) are derived
from / kept in sync with these. Stages communicate ONLY through these schemas.

Rotations are axis-angle in radians. `betas` is constant per sequence/clip.
`extra="forbid"` makes every model reject unknown fields, so CI fails on
malformed clips rather than silently dropping data.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# --- Fixed-length axis-angle / parameter vectors -------------------------------
# pydantic enforces exact length, which is the whole point of the contract:
# a 44-dim hand pose or 9-dim expression must be rejected, not coerced.
Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
BodyPose = Annotated[list[float], Field(min_length=63, max_length=63)]   # 21 joints * 3
HandPose = Annotated[list[float], Field(min_length=45, max_length=45)]   # 15 joints * 3 (full, NOT PCA)
Expression = Annotated[list[float], Field(min_length=10, max_length=10)]
Betas = Annotated[list[float], Field(min_length=10, max_length=10)]


class _Frozen(BaseModel):
    """Base: reject unknown keys so the contract stays frozen."""

    model_config = ConfigDict(extra="forbid")


# --- §3.1 SMPL-X frame & sequence ---------------------------------------------
class SMPLXFrame(_Frozen):
    global_orient: Vec3
    body_pose: BodyPose
    left_hand_pose: HandPose
    right_hand_pose: HandPose
    jaw_pose: Vec3
    # optional, zero-fill ok — defaulted so every serialized frame is complete
    # for the renderer (no None to special-case downstream).
    leye_pose: Vec3 = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    reye_pose: Vec3 = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    expression: Expression
    transl: Vec3 = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class SMPLXSequenceMeta(_Frozen):
    source_gloss: Optional[list[str]] = None
    clip_ids: Optional[list[str]] = None


class SMPLXSequence(_Frozen):
    model: Literal["SMPLX_NEUTRAL"]
    fps: float = Field(gt=0)
    betas: Betas
    frames: list[SMPLXFrame] = Field(min_length=1)
    meta: Optional[SMPLXSequenceMeta] = None


# --- §3.2 Dictionary clip ------------------------------------------------------
class SMPLXClipSource(_Frozen):
    video_url: Optional[str] = None
    license: Optional[str] = None
    extractor: Optional[str] = None


class SMPLXClip(_Frozen):
    clip_id: str = Field(min_length=1)
    gloss: str = Field(min_length=1)  # lexical gloss OR single letter for fingerspell
    kind: Literal["lexical", "letter"]
    fps: float = Field(gt=0)
    betas: Betas
    frames: list[SMPLXFrame] = Field(min_length=1)  # trimmed, rest-pose padded ends
    source: Optional[SMPLXClipSource] = None


# --- §3.3 Gloss sequence -------------------------------------------------------
# Tokens are either a lexical gloss ("HELLO") or a fingerspell directive ("fs:J").
class GlossSequence(_Frozen):
    english: str
    gloss: list[str]
    unmatched: Optional[list[str]] = None


# --- §3.4 Vapi -> backend webhook (subset) ------------------------------------
class VapiTranscriptWebhook(_Frozen):
    type: Literal["transcript"]
    transcript: str
    timestamp: float = 0


# --- §3.5 Runtime API ----------------------------------------------------------
class SignRequest(_Frozen):
    text: str


class SignError(_Frozen):
    error: str
    unmatched: list[str]


__all__ = [
    "SMPLXFrame",
    "SMPLXSequenceMeta",
    "SMPLXSequence",
    "SMPLXClipSource",
    "SMPLXClip",
    "GlossSequence",
    "VapiTranscriptWebhook",
    "SignRequest",
    "SignError",
]
