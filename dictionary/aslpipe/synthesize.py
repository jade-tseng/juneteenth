"""Procedural placeholder clips for the 18 seed entries.

WHY THIS EXISTS: real W6 clips come from SMPLer-X run on reference videos on a
GPU VM (see extract.py + gpu_vm/). That needs source footage and a GPU, neither
available at author time. These synthetic clips are schema-valid SMPLXClips with
smooth, rest-padded, *distinct* motion per sign so the downstream chain — lookup
(W3), concatenate+blend (W4), and the player (W5b) — can be built and demoed now.

They are NOT accurate ASL. Every clip is stamped source.extractor =
"synthetic-placeholder" so it is obvious which clips still need real extraction.
The one motion property we do honour: J is a trajectory, not a static pose
(CLAUDE.md §4.6 / risks) — the I-handshape hand traces a J through the air.
"""
from __future__ import annotations

import numpy as np

from .posekit import HAND_FINGERS, Frame, rest_pad

LEX_FRAMES = 30   # active frames for a lexical sign (~1.0s @30fps)
LET_FRAMES = 20   # active frames for a fingerspelled letter


def _smoothstep(u: float) -> float:
    return u * u * (3 - 2 * u)


def _ease_in_out(u: float) -> float:
    # rise to 1 by the midpoint, fall back — a single articulated "beat"
    return _smoothstep(min(u, 0.5) * 2) if u < 0.5 else _smoothstep((1 - u) * 2)


def _curl(hand: np.ndarray, **flex: float) -> None:
    """Set finger flexion. amount in radians; applied to all 3 joints of the
    finger (placeholder curl about the local z-axis)."""
    for finger, amount in flex.items():
        axis = 0 if finger == "thumb" else 2  # thumb folds on a different axis
        for j in HAND_FINGERS[finger]:
            v = [0.0, 0.0, 0.0]
            v[axis] = amount
            hand[3 * j:3 * j + 3] = v


# ── arm presets (right/left), eased by a 0..1 amplitude `a` ────────────────
def _right_up(f: Frame, a: float) -> None:
    """Right arm raised, hand near the face/shoulder (fingerspelling space)."""
    f.set_body("right_shoulder", [0.0, 0.0, -1.15 + 0.55 * a])
    f.set_body("right_elbow", [0.0, 0.0, 1.5 * a])

def _right_forward(f: Frame, a: float) -> None:
    f.set_body("right_shoulder", [-1.0 * a, 0.0, -1.15 + 1.0 * a])
    f.set_body("right_elbow", [0.0, 0.0, 0.3 * a])

def _right_chest(f: Frame, a: float) -> None:
    f.set_body("right_shoulder", [0.0, 0.0, -1.15 + 0.45 * a])
    f.set_body("right_elbow", [0.0, 0.0, 1.7 * a])

def _both_up(f: Frame, a: float) -> None:
    f.set_body("left_shoulder", [0.0, 0.0, 1.15 - 0.55 * a])
    f.set_body("right_shoulder", [0.0, 0.0, -1.15 + 0.55 * a])
    f.set_body("left_elbow", [0.0, 0.0, -1.4 * a])
    f.set_body("right_elbow", [0.0, 0.0, 1.4 * a])


def _base_rest(f: Frame) -> None:
    """Arms-down rest as the per-frame starting point (so a=0 == rest)."""
    f.set_body("left_shoulder", [0.0, 0.0, 1.15])
    f.set_body("right_shoulder", [0.0, 0.0, -1.15])
    f.set_body("left_elbow", [0.0, 0.0, -0.15])
    f.set_body("right_elbow", [0.0, 0.0, 0.15])


# ── lexical signs: (arm preset, motion) → frame(u) ─────────────────────────
def _lexical_frame(gloss: str, u: float) -> Frame:
    f = Frame()
    _base_rest(f)
    a = _ease_in_out(u)            # raise then lower over the clip
    osc = np.sin(u * np.pi * 4)    # in-gesture detail
    alt = np.sin(u * np.pi * 3)

    if gloss == "HELLO":
        _right_up(f, a)
        f.set_body("right_wrist", [0.0, 0.0, 0.3 * osc * a])   # small wave
        f.jaw_pose = np.array([0.04 * a, 0.0, 0.0])
    elif gloss == "HOW":
        _both_up(f, a)
        f.set_body("left_wrist", [0.4 * osc * a, 0.0, 0.0])
        f.set_body("right_wrist", [0.4 * osc * a, 0.0, 0.0])
    elif gloss == "YOU":
        _right_forward(f, a)
        _curl(f.right_hand_pose, middle=1.4, pinky=1.4, ring=1.4, thumb=0.6)  # index point
    elif gloss == "TODAY":
        _both_up(f, a * 0.7)
        f.transl = np.array([0.0, -0.05 * a, 0.0])             # settle downward
    elif gloss == "MY":
        _right_chest(f, a)                                     # flat palm to chest
    elif gloss == "NAME":
        _both_up(f, a)
        _curl(f.left_hand_pose, ring=1.4, pinky=1.4, thumb=0.8)   # H-hands
        _curl(f.right_hand_pose, ring=1.4, pinky=1.4, thumb=0.8)
        f.set_body("right_elbow", [0.15 * abs(osc) * a, 0.0, 1.4 * a])  # tap
    elif gloss == "ME":
        _right_chest(f, a)
        _curl(f.right_hand_pose, middle=1.4, pinky=1.4, ring=1.4, thumb=0.6)  # index to self
    elif gloss == "SIGN":
        _both_up(f, a)
        _curl(f.left_hand_pose, middle=1.4, ring=1.4, pinky=1.4)
        _curl(f.right_hand_pose, middle=1.4, ring=1.4, pinky=1.4)
        f.set_body("left_elbow", [0.0, 0.0, (1.0 + 0.4 * osc) * a])  # circular
        f.set_body("right_elbow", [0.0, 0.0, (1.0 - 0.4 * osc) * a])
    elif gloss == "NOT":
        _right_up(f, a * 0.8)
        _curl(f.right_hand_pose, index=1.4, middle=1.4, ring=1.4, pinky=1.4)  # A/thumb
        f.set_body("right_wrist", [-0.4 * a, 0.0, 0.0])        # flick out from chin
    elif gloss == "BUT":
        _both_up(f, a)
        _curl(f.left_hand_pose, middle=1.4, ring=1.4, pinky=1.4, thumb=0.6)
        _curl(f.right_hand_pose, middle=1.4, ring=1.4, pinky=1.4, thumb=0.6)
        f.set_body("left_wrist", [0.0, 0.5 * alt * a, 0.0])    # cross then part
        f.set_body("right_wrist", [0.0, -0.5 * alt * a, 0.0])
    elif gloss == "CAN":
        _both_up(f, a * 0.8)
        _curl(f.left_hand_pose, index=1.3, middle=1.3, ring=1.3, pinky=1.3)
        _curl(f.right_hand_pose, index=1.3, middle=1.3, ring=1.3, pinky=1.3)
        f.transl = np.array([0.0, -0.06 * a, 0.0])             # firm move down
    elif gloss == "HAPPY":
        _right_chest(f, a)
        f.transl = np.array([0.0, 0.05 * abs(osc) * a, 0.0])   # brush up chest
        f.jaw_pose = np.array([0.06 * a, 0.0, 0.0])            # slight smile-open
        f.expression = np.array([0.5 * a, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    elif gloss == "COMMUNICATE":
        _both_up(f, a)
        _curl(f.left_hand_pose, index=0.9, middle=0.9, ring=1.0, pinky=1.0, thumb=0.7)  # C
        _curl(f.right_hand_pose, index=0.9, middle=0.9, ring=1.0, pinky=1.0, thumb=0.7)
        f.set_body("left_elbow", [0.3 * alt * a, 0.0, 1.4 * a])   # alternate near mouth
        f.set_body("right_elbow", [-0.3 * alt * a, 0.0, 1.4 * a])
    else:
        _both_up(f, a)
    return f


# ── letter handshapes (right hand) ─────────────────────────────────────────
def _letter_handshape(letter: str, hand: np.ndarray) -> None:
    if letter == "A":
        _curl(hand, index=1.5, middle=1.5, ring=1.5, pinky=1.5, thumb=0.2)
    elif letter == "D":
        _curl(hand, middle=1.4, ring=1.4, pinky=1.4, thumb=0.9)            # index up
    elif letter == "E":
        _curl(hand, index=1.2, middle=1.2, ring=1.2, pinky=1.2, thumb=1.1)
    elif letter == "I":
        _curl(hand, index=1.5, middle=1.5, ring=1.5, thumb=1.0)            # pinky up
    elif letter == "J":
        _curl(hand, index=1.5, middle=1.5, ring=1.5, thumb=1.0)            # I-shape, will move


def _letter_frame(letter: str, u: float) -> Frame:
    f = Frame()
    _base_rest(f)
    a = _smoothstep(min(u * 2, 1.0))      # raise quickly, hold up
    _right_up(f, a)
    _letter_handshape(letter, f.right_hand_pose)

    if letter == "J":
        # Trace a J: the raised hand sweeps down, curves, and hooks. Driven by
        # the wrist over the back half of the clip so it reads as motion, not a
        # static pose (CLAUDE.md §4.6: "J is a motion letter").
        p = _smoothstep(max(0.0, (u - 0.3) / 0.7))   # 0..1 across the stroke
        f.set_body("right_wrist", [
            -1.2 * p,                        # sweep downward
            0.9 * np.sin(p * np.pi),         # curve out and back (the J belly)
            -0.7 * _smoothstep(max(0.0, (p - 0.6) / 0.4)),  # hook at the end
        ])
    return f


# ── public API ─────────────────────────────────────────────────────────────
def synthesize(gloss: str, kind: str) -> list[Frame]:
    """Return rest-padded frames for one entry (active span + eased rest ends)."""
    if kind == "letter":
        active = [_letter_frame(gloss, i / (LET_FRAMES - 1)) for i in range(LET_FRAMES)]
    else:
        active = [_lexical_frame(gloss, i / (LEX_FRAMES - 1)) for i in range(LEX_FRAMES)]
    return rest_pad(active, n=4)
