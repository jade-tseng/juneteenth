"""Coordinate normalization: camera-frame root -> front-facing, centered."""
from __future__ import annotations

import numpy as np

from aslpipe.posekit import Frame, normalize_root


def _rotated_frame(global_orient, transl):
    f = Frame()
    f.global_orient = np.asarray(global_orient, dtype=float)
    f.transl = np.asarray(transl, dtype=float)
    # give the body some local pose so we can confirm it is preserved
    f.set_body("right_elbow", [0.0, 0.0, 1.0])
    return f


def test_first_frame_root_goes_to_identity():
    # camera-frame yaw of 2.5 rad on frame 0 should be removed.
    frames = [_rotated_frame([0.0, 2.5, 0.0], [0.3, 1.0, 4.0]) for _ in range(3)]
    out = normalize_root(frames)
    assert np.allclose(out[0].global_orient, [0.0, 0.0, 0.0], atol=1e-6)


def test_first_frame_translation_centered():
    frames = [_rotated_frame([0.1, 0.2, 0.3], [0.5, 1.5, 4.0]) for _ in range(2)]
    out = normalize_root(frames)
    assert np.allclose(out[0].transl, [0.0, 0.0, 0.0], atol=1e-6)


def test_relative_motion_preserved():
    # frame 1 turns +0.3 rad about Y relative to frame 0's 2.5 rad camera yaw.
    f0 = _rotated_frame([0.0, 2.5, 0.0], [0.0, 0.0, 4.0])
    f1 = _rotated_frame([0.0, 2.8, 0.0], [0.0, 0.0, 4.0])
    out = normalize_root([f0, f1])
    # after removing the camera yaw, frame 1's residual root is ~+0.3 about Y.
    assert np.allclose(out[1].global_orient, [0.0, 0.3, 0.0], atol=1e-4)


def test_local_body_pose_untouched():
    frames = [_rotated_frame([0.0, 1.0, 0.0], [1.0, 1.0, 1.0]) for _ in range(2)]
    before = frames[0].body_pose.copy()
    out = normalize_root(frames)
    assert np.allclose(out[0].body_pose, before)  # body/hand poses are local


def test_input_not_mutated():
    frames = [_rotated_frame([0.0, 2.5, 0.0], [0.5, 1.0, 4.0])]
    orig = frames[0].global_orient.copy()
    normalize_root(frames)
    assert np.allclose(frames[0].global_orient, orig)


def test_empty_is_noop():
    assert normalize_root([]) == []
