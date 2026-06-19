"""Post-process raw SMPLer-X output into clip-ready frames (CLAUDE.md §4.6).

Order matters: trim to the active sign first, smooth the jitter, resample to the
dictionary fps, then rest-pad the ends so clips concatenate cleanly (W4). Manual
cleanup is still expected on top of this — extraction quality bounds clip quality.
"""
from __future__ import annotations

from .posekit import Frame, normalize_root, rest_pad, resample, smooth, trim_to_motion


def clean_frames(
    frames: list[Frame],
    *,
    src_fps: float,
    dst_fps: float = 30.0,
    smooth_window: int = 5,
    pad: int = 4,
    normalize: bool = True,
) -> list[Frame]:
    # Camera-frame extractions (SMPLer-X, SignAvatars) carry a camera-relative
    # root pose; normalize first so the avatar faces front and is centered (W5).
    if normalize:
        frames = normalize_root(frames)
    frames = trim_to_motion(frames)
    frames = smooth(frames, window=smooth_window)
    frames = resample(frames, src_fps=src_fps, dst_fps=dst_fps)
    frames = rest_pad(frames, n=pad)
    return frames
