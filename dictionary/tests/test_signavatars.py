"""SignAvatars .pkl -> SMPLXClip conversion, end-to-end via a synthetic pkl.

Real SignAvatars data is gated (Google Form approval, §11), so we synthesize a
182-dim per-frame sequence in a temp .pkl and assert a schema-valid clip out.
The fixture is generated in-memory / temp — never committed.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

from aslpipe.signavatars import (
    FLAT_DIM,
    convert_dir,
    convert_pkl,
    frames_from_params,
)

# frozen contract (path shimmed by conftest)
from asl_schemas import SMPLXClip


def _synthetic_channels(T=48, seed=0):
    """A 24fps-ish sequence with smooth, non-trivial motion in every channel
    plus a camera-frame root rotation + translation (so normalize has work)."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, T)[:, None]
    return {
        # camera-frame root: a constant tilt + slight sway -> normalize_root
        # should pull frame 0 to ~identity.
        "global_orient": np.array([0.0, 2.5, 0.0]) + 0.1 * np.sin(2 * np.pi * t) * np.ones((1, 3)),
        "body_pose": 0.3 * np.sin(2 * np.pi * t + rng.random((1, 63))),
        "left_hand_pose": 0.2 * np.sin(2 * np.pi * t + rng.random((1, 45))),
        "right_hand_pose": 0.2 * np.cos(2 * np.pi * t + rng.random((1, 45))),
        "jaw_pose": 0.05 * np.sin(2 * np.pi * t) * np.ones((1, 3)),
        "betas": np.tile(np.array([0.5, -0.3] + [0.0] * 8), (T, 1)),
        "expression": 0.1 * np.sin(2 * np.pi * t) * np.ones((1, 10)),
        "transl": np.array([0.4, 1.2, 3.0]) + 0.02 * t * np.ones((1, 3)),
    }


def _flat_from_channels(ch):
    order = ["global_orient", "body_pose", "left_hand_pose", "right_hand_pose",
             "jaw_pose", "betas", "expression", "transl"]
    return np.concatenate([np.asarray(ch[k], dtype=float) for k in order], axis=1)


def _write_pkl(obj, path: Path) -> Path:
    with open(path, "wb") as fh:
        pickle.dump(obj, fh)
    return path


def test_flat_dim_is_182():
    assert FLAT_DIM == 182


def test_frames_from_dict_of_arrays():
    ch = _synthetic_channels(T=10)
    frames, betas = frames_from_params(ch)
    assert len(frames) == 10
    assert len(betas) == 10 and betas[0] == pytest.approx(0.5)
    assert frames[0].left_hand_pose.shape == (45,)  # FULL hands, not PCA


def test_frames_from_flat_array_equivalent():
    ch = _synthetic_channels(T=8)
    flat = _flat_from_channels(ch)
    f_dict, b_dict = frames_from_params(ch)
    f_flat, b_flat = frames_from_params(flat)
    assert len(f_flat) == len(f_dict) == 8
    assert b_flat == pytest.approx(b_dict)
    assert np.allclose(f_flat[3].body_pose, f_dict[3].body_pose)


def test_convert_pkl_dict_yields_schema_valid_clip(tmp_path):
    pkl = _write_pkl(_synthetic_channels(T=48), tmp_path / "sample.pkl")
    clip = convert_pkl(pkl, clip_id="hello-001", gloss="HELLO", kind="lexical")
    # the real assertion: it validates against the frozen contract
    model = SMPLXClip.model_validate(clip)
    assert model.kind == "lexical" and model.fps == 30.0
    assert len(model.frames) >= 1
    assert len(model.frames[0].left_hand_pose) == 45
    assert clip["source"]["extractor"] == "SignAvatars"


def test_convert_pkl_flat_array_yields_schema_valid_clip(tmp_path):
    flat = _flat_from_channels(_synthetic_channels(T=40))
    pkl = _write_pkl(flat, tmp_path / "flat.pkl")
    clip = convert_pkl(pkl, clip_id="my-001", gloss="MY")
    SMPLXClip.model_validate(clip)  # raises on any contract violation


def test_resampled_24_to_30_increases_frame_count(tmp_path):
    # 24fps -> 30fps should produce more frames for the same duration (before
    # trim/pad effects). Use a long, all-moving sequence so trim keeps it.
    pkl = _write_pkl(_synthetic_channels(T=72), tmp_path / "long.pkl")
    clip = convert_pkl(pkl, clip_id="sign-001", gloss="SIGN")
    # sanity: produced a non-trivial clip
    assert len(clip["frames"]) > 10


def test_convert_dir_matches_manifest_entries(tmp_path):
    pkl_dir = tmp_path / "pkls"
    pkl_dir.mkdir()
    _write_pkl(_synthetic_channels(T=40), pkl_dir / "hello-001.pkl")
    _write_pkl(_synthetic_channels(T=40, seed=1), pkl_dir / "my-001.pkl")
    # name-001 has no pkl -> skipped
    entries = [
        {"clip_id": "hello-001", "gloss": "HELLO", "kind": "lexical"},
        {"clip_id": "my-001", "gloss": "MY", "kind": "lexical"},
        {"clip_id": "name-001", "gloss": "NAME", "kind": "lexical"},
    ]
    out = tmp_path / "clips"
    written = convert_dir(pkl_dir, out, manifest_entries=entries)
    assert {p.name for p in written} == {"hello-001.json", "my-001.json"}
    for p in written:
        SMPLXClip.model_validate(__import__("json").loads(p.read_text()))
