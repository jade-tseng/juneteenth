"""Concatenate + slerp-blend clips into one SMPLXSequence (W4, §4.4).

Input: ordered SMPLXClip[]  ->  Output: one continuous SMPLXSequence.
- Rotation fields (global_orient, body/hand/jaw/eye poses) blend per joint via
  slerp over K transition frames; expression/transl lerp (not rotations).
- Clips are resampled to a common fps; betas are held constant per sequence.
- Optional rest hold (repeat the boundary frame) between words.
"""

from __future__ import annotations

import numpy as np
from asl_schemas import SMPLXClip, SMPLXFrame, SMPLXSequence, SMPLXSequenceMeta

from .rotation import slerp_axis_angle

# Field -> number of 3-DOF joints. expression/transl are NOT rotations (lerp).
_ROTATION_FIELDS = {
    "global_orient": 1,
    "body_pose": 21,
    "left_hand_pose": 15,
    "right_hand_pose": 15,
    "jaw_pose": 1,
    "leye_pose": 1,
    "reye_pose": 1,
}
_LERP_FIELDS = ("expression", "transl")


def _frame_to_arrays(frame: SMPLXFrame) -> dict[str, np.ndarray]:
    d = frame.model_dump()
    return {k: np.asarray(v, dtype=float) for k, v in d.items()}


def _arrays_to_frame(arrays: dict[str, np.ndarray]) -> SMPLXFrame:
    return SMPLXFrame(**{k: v.tolist() for k, v in arrays.items()})


def _blend_frames(a: dict, b: dict, t: float) -> dict:
    """Interpolate between two frame-array dicts at fraction t in [0, 1]."""
    out: dict[str, np.ndarray] = {}
    for field, n_joints in _ROTATION_FIELDS.items():
        aa_a = a[field].reshape(n_joints, 3)
        aa_b = b[field].reshape(n_joints, 3)
        out[field] = slerp_axis_angle(aa_a, aa_b, t).reshape(-1)
    for field in _LERP_FIELDS:
        out[field] = (1.0 - t) * a[field] + t * b[field]
    return out


def _resample(frames: list[dict], src_fps: float, dst_fps: float) -> list[dict]:
    """Resample a frame list to dst_fps with per-joint slerp interpolation."""
    if abs(src_fps - dst_fps) < 1e-6 or len(frames) < 2:
        return frames
    duration = (len(frames) - 1) / src_fps
    n_out = max(2, int(round(duration * dst_fps)) + 1)
    out: list[dict] = []
    for i in range(n_out):
        # map output index to a fractional source index
        src_pos = (i / (n_out - 1)) * (len(frames) - 1)
        lo = int(np.floor(src_pos))
        hi = min(lo + 1, len(frames) - 1)
        frac = src_pos - lo
        out.append(_blend_frames(frames[lo], frames[hi], frac) if hi != lo else frames[lo])
    return out


def concatenate(
    clips: list[SMPLXClip],
    transition_frames: int = 6,
    fps: float | None = None,
    rest_hold_frames: int = 0,
) -> SMPLXSequence:
    """Blend an ordered clip list into one SMPLXSequence.

    transition_frames: K frames of slerp blend inserted between adjacent clips.
    rest_hold_frames: optional frames holding the boundary pose between words.
    """
    if not clips:
        raise ValueError("concatenate requires at least one clip")

    dst_fps = float(fps if fps is not None else clips[0].fps)
    betas = list(clips[0].betas)  # fixed neutral betas for the whole sequence

    out_frames: list[dict] = []
    prev_last: dict | None = None
    spans: list[list[int]] = []  # [start, end) of each clip's own frames

    for clip in clips:
        cframes = [_frame_to_arrays(f) for f in clip.frames]
        cframes = _resample(cframes, float(clip.fps), dst_fps)

        if prev_last is not None:
            for _ in range(rest_hold_frames):
                out_frames.append(prev_last)
            # K interior transition frames: t strictly between 0 and 1
            for k in range(1, transition_frames + 1):
                t = k / (transition_frames + 1)
                out_frames.append(_blend_frames(prev_last, cframes[0], t))

        start = len(out_frames)
        out_frames.extend(cframes)
        spans.append([start, len(out_frames)])  # this clip's own frames
        prev_last = cframes[-1]

    return SMPLXSequence(
        model="SMPLX_NEUTRAL",
        fps=dst_fps,
        betas=betas,
        frames=[_arrays_to_frame(f) for f in out_frames],
        meta=SMPLXSequenceMeta(
            source_gloss=[c.gloss for c in clips],
            clip_ids=[c.clip_id for c in clips],
            clip_frame_spans=spans,
        ),
    )
