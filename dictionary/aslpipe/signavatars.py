"""SignAvatars `.pkl` -> SMPLXClip converter (real-clip path, dataset route B).

SignAvatars (https://signavatars.github.io/) is a motion-capture-grade SMPL-X
sign-language dataset, gated behind a Google Form approval (CLAUDE.md §11,
non-commercial). Once approved, each sign comes as a pickled per-frame SMPL-X
parameter sequence. This converts one such `.pkl` into a schema-valid §3.2
SMPLXClip via the existing clean -> build pipeline.

Expected per-frame parameter layout (182 dims, the SignAvatars convention):
  global_orient   3
  body_pose      63   (21 body joints * 3)
  left_hand_pose 45   (FULL 15 joints * 3 — NOT PCA)
  right_hand_pose45
  jaw_pose        3
  betas          10   (constant per sequence; we take frame 0's)
  expression     10
  transl          3
                ---
                182
Native fps is 24; we resample to the dictionary's 30 via clean_frames.

The `.pkl` may store this as:
  * a dict of arrays {"global_orient": (T,3), "body_pose": (T,63), ...}, or
  * a single (T, 182) / (182,) array in the order above.
Both are handled by `frames_from_params`.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

from .build_clip import build_clip, write_clip
from .clean import clean_frames
from .posekit import BETAS_DIM, BODY_DIM, EXPR_DIM, HAND_DIM, Frame

SIGNAVATARS_FPS = 24.0

# (field, dim) in the flat 182-dim order. betas is per-sequence, not per-frame
# (it is constant), but SignAvatars repeats it per frame; we slice it out and
# take frame 0's value for the clip's `betas`.
_FLAT_LAYOUT: list[tuple[str, int]] = [
    ("global_orient", 3),
    ("body_pose", BODY_DIM),       # 63
    ("left_hand_pose", HAND_DIM),  # 45
    ("right_hand_pose", HAND_DIM), # 45
    ("jaw_pose", 3),
    ("betas", BETAS_DIM),          # 10
    ("expression", EXPR_DIM),      # 10
    ("transl", 3),
]
FLAT_DIM = sum(d for _, d in _FLAT_LAYOUT)  # 182


def load_pkl(path: Path) -> Any:
    with open(path, "rb") as fh:
        return pickle.load(fh)  # noqa: S301 (trusted, locally-downloaded dataset)


def _as_2d(arr: np.ndarray, dim: int) -> np.ndarray:
    """Coerce (dim,) -> (1, dim); validate (T, dim)."""
    a = np.asarray(arr, dtype=float)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if a.shape[1] != dim:
        raise ValueError(f"expected last-dim {dim}, got {a.shape[1]}")
    return a


def _split_flat(flat: np.ndarray) -> dict[str, np.ndarray]:
    """Split a (T, 182) array into named per-frame channels."""
    flat = _as_2d(flat, FLAT_DIM)
    out: dict[str, np.ndarray] = {}
    off = 0
    for name, dim in _FLAT_LAYOUT:
        out[name] = flat[:, off:off + dim]
        off += dim
    return out


def _channels_from_obj(obj: Any) -> dict[str, np.ndarray]:
    """Normalise a loaded pkl (dict-of-arrays OR flat array) into named (T,*)
    channels covering the _FLAT_LAYOUT fields (missing optional ones zero-fill)."""
    if isinstance(obj, dict):
        # may be nested under common keys
        for key in ("smplx", "smplx_params", "params", "poses"):
            if key in obj and isinstance(obj[key], dict):
                obj = obj[key]
                break
        # a flat array stored under a key
        if "params" in obj and isinstance(obj["params"], np.ndarray):
            return _split_flat(obj["params"])
        channels: dict[str, np.ndarray] = {}
        dims = dict(_FLAT_LAYOUT)
        # determine T from any present body/global channel
        ref = obj.get("body_pose", obj.get("global_orient"))
        T = _as_2d(np.asarray(ref, dtype=float), dims["body_pose" if "body_pose" in obj else "global_orient"]).shape[0]
        for name, dim in _FLAT_LAYOUT:
            if name in obj:
                channels[name] = _as_2d(np.asarray(obj[name], dtype=float), dim)
            else:
                channels[name] = np.zeros((T, dim))
        return channels
    # plain array: must be the flat 182-dim layout
    return _split_flat(np.asarray(obj, dtype=float))


def frames_from_params(obj: Any) -> tuple[list[Frame], list[float]]:
    """Convert a loaded SignAvatars pkl object into posekit Frames + betas.

    Returns (frames, betas). betas is taken from frame 0 (constant per sequence).
    leye/reye are zero-filled (SignAvatars has no eye pose); they are optional.
    """
    ch = _channels_from_obj(obj)
    T = ch["global_orient"].shape[0]
    betas = ch["betas"][0].tolist() if "betas" in ch else [0.0] * BETAS_DIM

    frames: list[Frame] = []
    for i in range(T):
        frames.append(Frame(
            global_orient=ch["global_orient"][i].copy(),
            body_pose=ch["body_pose"][i].copy(),
            left_hand_pose=ch["left_hand_pose"][i].copy(),
            right_hand_pose=ch["right_hand_pose"][i].copy(),
            jaw_pose=ch["jaw_pose"][i].copy(),
            expression=ch["expression"][i].copy(),
            transl=ch["transl"][i].copy(),
        ))
    return frames, betas


def convert_pkl(
    pkl_path: Path,
    *,
    clip_id: str,
    gloss: str,
    kind: str = "lexical",
    dst_fps: float = 30.0,
    src_fps: float = SIGNAVATARS_FPS,
    video_url: str | None = None,
    license: str = "CC-BY-NC",
    extractor: str = "SignAvatars",
) -> dict:
    """Load one SignAvatars `.pkl`, clean (normalize/trim/smooth/resample/pad),
    and build a schema-validated SMPLXClip dict."""
    obj = load_pkl(Path(pkl_path))
    frames, betas = frames_from_params(obj)
    frames = clean_frames(frames, src_fps=src_fps, dst_fps=dst_fps)
    return build_clip(
        clip_id=clip_id, gloss=gloss, kind=kind, fps=dst_fps,
        frames=frames, betas=betas,
        video_url=video_url, license=license, extractor=extractor,
    )


def convert_dir(
    pkl_dir: Path,
    out_dir: Path,
    *,
    manifest_entries: list[dict],
    dst_fps: float = 30.0,
    src_fps: float = SIGNAVATARS_FPS,
    license: str = "CC-BY-NC",
) -> list[Path]:
    """Convert every manifest entry that has a matching `<clip_id>.pkl` in
    `pkl_dir`, writing validated clips into `out_dir`. Returns written paths.

    `manifest_entries` items: {clip_id, gloss, kind, [pkl?]}. The pkl filename
    defaults to `<clip_id>.pkl`.
    """
    pkl_dir = Path(pkl_dir)
    written: list[Path] = []
    for e in manifest_entries:
        pkl_name = e.get("pkl", f"{e['clip_id']}.pkl")
        pkl_path = pkl_dir / pkl_name
        if not pkl_path.exists():
            continue
        clip = convert_pkl(
            pkl_path,
            clip_id=e["clip_id"], gloss=e["gloss"], kind=e.get("kind", "lexical"),
            dst_fps=dst_fps, src_fps=src_fps,
            video_url=e.get("video_url"), license=license,
        )
        written.append(write_clip(clip, Path(out_dir)))
    return written
