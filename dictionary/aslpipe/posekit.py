"""SMPL-X pose toolkit for the W6 dictionary build.

Everything here operates on the §3.1 frame layout (axis-angle, radians):
  global_orient[3], body_pose[63], left_hand_pose[45], right_hand_pose[45],
  jaw_pose[3], leye/reye[3], expression[10], transl[3].

Two consumers share it:
  * clean.py   — post-process SMPLer-X output (trim / smooth / rest-pad / resample)
  * synthesize.py — author placeholder clips procedurally until real extraction runs

Smoothing is done on rotation *vectors* via quaternion slerp interpolation and a
quaternion running mean, never by averaging raw axis-angle (the W4 seam rule:
"never lerp raw axis-angle"). betas are constant per clip; transl/eyes zero-fill.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

# ── dimensions ────────────────────────────────────────────────────────────
N_BODY = 21          # body joints (each * 3 -> 63)
N_HAND = 15          # finger joints per hand (each * 3 -> 45)
BODY_DIM = N_BODY * 3
HAND_DIM = N_HAND * 3
EXPR_DIM = 10
BETAS_DIM = 10

# ── SMPL-X body joint indices (into body_pose, joint j -> [3j:3j+3]) ────────
# Order per the SMPL-X body kinematic tree (pelvis is global_orient, excluded).
BODY = {
    "left_hip": 0, "right_hip": 1, "spine1": 2, "left_knee": 3, "right_knee": 4,
    "spine2": 5, "left_ankle": 6, "right_ankle": 7, "spine3": 8,
    "left_foot": 9, "right_foot": 10, "neck": 11, "left_collar": 12,
    "right_collar": 13, "head": 14, "left_shoulder": 15, "right_shoulder": 16,
    "left_elbow": 17, "right_elbow": 18, "left_wrist": 19, "right_wrist": 20,
}

# MANO finger joint groups within a 15-joint hand (each finger = 3 joints).
HAND_FINGERS = {
    "index": (0, 1, 2), "middle": (3, 4, 5), "pinky": (6, 7, 8),
    "ring": (9, 10, 11), "thumb": (12, 13, 14),
}


@dataclass
class Frame:
    """One SMPL-X frame as numpy arrays; .to_dict() emits the §3.1 JSON shape."""
    global_orient: np.ndarray = field(default_factory=lambda: np.zeros(3))
    body_pose: np.ndarray = field(default_factory=lambda: np.zeros(BODY_DIM))
    left_hand_pose: np.ndarray = field(default_factory=lambda: np.zeros(HAND_DIM))
    right_hand_pose: np.ndarray = field(default_factory=lambda: np.zeros(HAND_DIM))
    jaw_pose: np.ndarray = field(default_factory=lambda: np.zeros(3))
    leye_pose: np.ndarray = field(default_factory=lambda: np.zeros(3))
    reye_pose: np.ndarray = field(default_factory=lambda: np.zeros(3))
    expression: np.ndarray = field(default_factory=lambda: np.zeros(EXPR_DIM))
    transl: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def copy(self) -> "Frame":
        return Frame(
            self.global_orient.copy(), self.body_pose.copy(),
            self.left_hand_pose.copy(), self.right_hand_pose.copy(),
            self.jaw_pose.copy(), self.leye_pose.copy(), self.reye_pose.copy(),
            self.expression.copy(), self.transl.copy(),
        )

    def set_body(self, joint: str, rot: Iterable[float]) -> "Frame":
        i = BODY[joint] * 3
        self.body_pose[i:i + 3] = rot
        return self

    def to_dict(self) -> dict:
        r = lambda a: [round(float(x), 6) for x in a]
        return {
            "global_orient": r(self.global_orient),
            "body_pose": r(self.body_pose),
            "left_hand_pose": r(self.left_hand_pose),
            "right_hand_pose": r(self.right_hand_pose),
            "jaw_pose": r(self.jaw_pose),
            "leye_pose": r(self.leye_pose),
            "reye_pose": r(self.reye_pose),
            "expression": r(self.expression),
            "transl": r(self.transl),
        }


def rest_frame() -> Frame:
    """Neutral rest: arms relaxed at the sides. Used to pad clip ends so
    concatenation (W4) blends from/to a known pose at every seam."""
    f = Frame()
    # bring the canonical T-pose arms down to the sides (rotate shoulders)
    f.set_body("left_shoulder", [0.0, 0.0, 1.15])
    f.set_body("right_shoulder", [0.0, 0.0, -1.15])
    f.set_body("left_elbow", [0.0, 0.0, -0.15])
    f.set_body("right_elbow", [0.0, 0.0, 0.15])
    return f


# ── axis-angle <-> quaternion (for slerp-correct smoothing) ────────────────
def _aa_to_quat(aa: np.ndarray) -> np.ndarray:
    theta = np.linalg.norm(aa)
    if theta < 1e-8:
        return np.array([0.0, 0.0, 0.0, 1.0])
    axis = aa / theta
    h = theta / 2.0
    return np.concatenate([axis * np.sin(h), [np.cos(h)]])


def _quat_to_aa(q: np.ndarray) -> np.ndarray:
    q = q / (np.linalg.norm(q) + 1e-12)
    if q[3] < 0:  # canonical hemisphere
        q = -q
    w = np.clip(q[3], -1.0, 1.0)
    theta = 2.0 * np.arccos(w)
    s = np.sqrt(max(1.0 - w * w, 1e-12))
    if s < 1e-6:
        return np.zeros(3)
    return (q[:3] / s) * theta


def _slerp(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    if np.dot(q0, q1) < 0:
        q1 = -q1
    dot = np.clip(np.dot(q0, q1), -1.0, 1.0)
    if dot > 0.9995:
        return q0 + t * (q1 - q0)
    omega = np.arccos(dot)
    so = np.sin(omega)
    return (np.sin((1 - t) * omega) / so) * q0 + (np.sin(t * omega) / so) * q1


def slerp_aa(a0: np.ndarray, a1: np.ndarray, t: float) -> np.ndarray:
    """Interpolate two axis-angle rotations through quaternion slerp."""
    return _quat_to_aa(_slerp(_aa_to_quat(a0), _aa_to_quat(a1), t))


def _smooth_rotvec_channel(seq: np.ndarray, window: int) -> np.ndarray:
    """Moving quaternion mean over a (T,3) axis-angle channel."""
    T = len(seq)
    if T < 3 or window < 3:
        return seq
    half = window // 2
    out = np.empty_like(seq)
    quats = np.array([_aa_to_quat(seq[i]) for i in range(T)])
    for i in range(T):
        lo, hi = max(0, i - half), min(T, i + half + 1)
        acc = np.zeros(4)
        for j in range(lo, hi):
            q = quats[j]
            if np.dot(q, quats[i]) < 0:
                q = -q
            acc += q
        out[i] = _quat_to_aa(acc / np.linalg.norm(acc))
    return out


# ── sequence-level operations ──────────────────────────────────────────────
_ROT_FIELDS = ("global_orient", "jaw_pose", "leye_pose", "reye_pose")
_POSE_FIELDS = ("body_pose", "left_hand_pose", "right_hand_pose")


def smooth(frames: list[Frame], window: int = 5) -> list[Frame]:
    """Temporal smoothing on every rotation channel via quaternion mean;
    expression/transl get a plain moving average (they are not rotations)."""
    if len(frames) < 3:
        return frames
    out = [f.copy() for f in frames]

    for field_name in _ROT_FIELDS:
        seq = np.array([getattr(f, field_name) for f in frames])  # (T,3)
        sm = _smooth_rotvec_channel(seq, window)
        for i, f in enumerate(out):
            setattr(f, field_name, sm[i])

    for field_name in _POSE_FIELDS:
        seq = np.array([getattr(f, field_name) for f in frames])  # (T, K*3)
        K = seq.shape[1] // 3
        for k in range(K):
            sm = _smooth_rotvec_channel(seq[:, 3 * k:3 * k + 3], window)
            for i, f in enumerate(out):
                getattr(f, field_name)[3 * k:3 * k + 3] = sm[i]

    # non-rotation channels: simple centered moving average
    for field_name in ("expression", "transl"):
        seq = np.array([getattr(f, field_name) for f in frames])
        kernel = np.ones(window) / window
        sm = np.vstack([
            np.convolve(seq[:, c], kernel, mode="same") for c in range(seq.shape[1])
        ]).T
        for i, f in enumerate(out):
            setattr(f, field_name, sm[i])
    return out


def trim_to_motion(frames: list[Frame], eps: float = 0.02, pad: int = 2) -> list[Frame]:
    """Drop leading/trailing dead frames where the pose barely changes,
    keeping `pad` frames of margin. Bounds the clip to the active sign."""
    if len(frames) < 3:
        return frames
    poses = np.array([
        np.concatenate([f.body_pose, f.left_hand_pose, f.right_hand_pose])
        for f in frames
    ])
    vel = np.linalg.norm(np.diff(poses, axis=0), axis=1)
    moving = np.where(vel > eps)[0]
    if len(moving) == 0:
        return frames
    lo = max(0, moving[0] - pad)
    hi = min(len(frames), moving[-1] + 2 + pad)
    return frames[lo:hi]


def rest_pad(frames: list[Frame], n: int = 4) -> list[Frame]:
    """Ease into/out of the rest pose at both ends (§3.2 'rest-pose padded
    ends') so clips concatenate without a jump at the seams."""
    if not frames:
        return frames
    rest = rest_frame()
    head = [_blend(rest, frames[0], (i + 1) / (n + 1)) for i in range(n)]
    tail = [_blend(frames[-1], rest, (i + 1) / (n + 1)) for i in range(n)]
    return head + frames + tail


def _blend(a: Frame, b: Frame, t: float) -> Frame:
    """Slerp every rotation channel; lerp expression/transl."""
    out = Frame()
    out.global_orient = slerp_aa(a.global_orient, b.global_orient, t)
    out.jaw_pose = slerp_aa(a.jaw_pose, b.jaw_pose, t)
    for field_name in _POSE_FIELDS:
        av, bv = getattr(a, field_name), getattr(b, field_name)
        ov = getattr(out, field_name)
        for k in range(len(av) // 3):
            ov[3 * k:3 * k + 3] = slerp_aa(av[3 * k:3 * k + 3], bv[3 * k:3 * k + 3], t)
    out.expression = (1 - t) * a.expression + t * b.expression
    out.transl = (1 - t) * a.transl + t * b.transl
    return out


def normalize_root(frames: list[Frame]) -> list[Frame]:
    """Front-face + center a camera-frame sequence (load-bearing for W5).

    SMPLer-X / SignAvatars output is in the *camera* frame: `global_orient`
    carries the subject's orientation relative to the camera and `transl` their
    position in view. Fed straight to the renderer the avatar comes out rotated
    and off-screen. This removes that camera pose while preserving the sign's
    own articulation:

      * Take the first frame's root rotation R0 as the reference orientation.
        Left-multiply every frame's global_orient by R0^-1 so frame 0 faces
        front (root ≈ identity) and later frames keep their motion *relative*
        to frame 0 (turning the torso mid-sign is preserved).
      * Subtract frame 0's translation from every frame and zero its depth, so
        the avatar is centered at the origin. Body/hand/jaw poses are local to
        the kinematic tree and are left untouched.

    Returns new frames; input is not mutated.
    """
    if not frames:
        return frames
    out = [f.copy() for f in frames]

    # reference: inverse of frame 0's root rotation (axis-angle -> quaternion).
    q0 = _aa_to_quat(frames[0].global_orient)
    q0_inv = np.array([-q0[0], -q0[1], -q0[2], q0[3]])  # conjugate (unit quat)
    t0 = frames[0].transl.copy()

    for i, f in enumerate(out):
        q = _aa_to_quat(frames[i].global_orient)
        q_norm = _quat_mul(q0_inv, q)
        f.global_orient = _quat_to_aa(q_norm)
        # re-center: drop frame 0's position; zero depth so the avatar sits at origin.
        f.transl = frames[i].transl - t0
    return out


def _quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product of two [x,y,z,w] quaternions."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ])


def resample(frames: list[Frame], src_fps: float, dst_fps: float) -> list[Frame]:
    """Resample to a common fps (§4.4) via per-channel slerp; betas unaffected."""
    if abs(src_fps - dst_fps) < 1e-6 or len(frames) < 2:
        return frames
    dur = (len(frames) - 1) / src_fps
    n_out = max(2, int(round(dur * dst_fps)) + 1)
    out = []
    for i in range(n_out):
        u = (i / (n_out - 1)) * (len(frames) - 1)
        lo = int(np.floor(u))
        hi = min(lo + 1, len(frames) - 1)
        out.append(_blend(frames[lo], frames[hi], u - lo))
    return out
