"""Axis-angle <-> quaternion + per-joint slerp (W4 core).

Axis-angle rotations must be interpolated as rotations (slerp), never lerped
componentwise — lerping raw axis-angle produces seam artifacts at clip
boundaries (CLAUDE.md §10). Quaternions are (w, x, y, z).
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-8


def aa_to_quat(aa: np.ndarray) -> np.ndarray:
    """(..., 3) axis-angle -> (..., 4) quaternion (w, x, y, z)."""
    aa = np.asarray(aa, dtype=float)
    angle = np.linalg.norm(aa, axis=-1, keepdims=True)  # (..., 1)
    small = angle < _EPS
    safe_angle = np.where(small, 1.0, angle)
    axis = aa / safe_angle
    half = angle * 0.5
    w = np.cos(half)
    xyz = axis * np.sin(half)
    quat = np.concatenate([w, xyz], axis=-1)
    # angle ~ 0 -> identity quaternion
    identity = np.zeros_like(quat)
    identity[..., 0] = 1.0
    return np.where(small, identity, quat)


def quat_to_aa(q: np.ndarray) -> np.ndarray:
    """(..., 4) quaternion -> (..., 3) axis-angle."""
    q = np.asarray(q, dtype=float)
    q = q / np.clip(np.linalg.norm(q, axis=-1, keepdims=True), _EPS, None)
    # canonical hemisphere (w >= 0) so angle stays in [0, pi]
    q = np.where(q[..., :1] < 0, -q, q)
    w = np.clip(q[..., :1], -1.0, 1.0)
    angle = 2.0 * np.arccos(w)               # (..., 1)
    s = np.sqrt(np.clip(1.0 - w * w, 0.0, None))
    small = s < _EPS
    safe_s = np.where(small, 1.0, s)
    axis = q[..., 1:] / safe_s
    aa = axis * angle
    return np.where(small, np.zeros_like(aa), aa)


def slerp_quat(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    """Per-row slerp between two (..., 4) quaternion arrays."""
    q0 = np.asarray(q0, dtype=float)
    q1 = np.asarray(q1, dtype=float)
    dot = np.sum(q0 * q1, axis=-1, keepdims=True)
    # take the shorter arc
    q1 = np.where(dot < 0, -q1, q1)
    dot = np.abs(dot)

    out = np.empty_like(q0)
    # near-parallel: linear interpolate + renormalize (slerp is numerically unstable)
    lin = dot > (1.0 - 1e-6)
    theta = np.arccos(np.clip(dot, -1.0, 1.0))
    sin_theta = np.sin(theta)
    safe_sin = np.where(sin_theta < _EPS, 1.0, sin_theta)
    w0 = np.sin((1.0 - t) * theta) / safe_sin
    w1 = np.sin(t * theta) / safe_sin
    slerped = w0 * q0 + w1 * q1
    lerped = (1.0 - t) * q0 + t * q1
    out = np.where(lin, lerped, slerped)
    return out / np.clip(np.linalg.norm(out, axis=-1, keepdims=True), _EPS, None)


def slerp_axis_angle(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """Slerp between two axis-angle arrays of shape (n_joints, 3)."""
    return quat_to_aa(slerp_quat(aa_to_quat(a), aa_to_quat(b), t))
