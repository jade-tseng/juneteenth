"""W4 acceptance: one continuous SMPLXSequence, slerp blend, no seam jump."""

from __future__ import annotations

import math

import numpy as np
from asl_schemas import SMPLXSequence
from conftest import clip, frame

from app.blend import concatenate
from app.blend.rotation import aa_to_quat, slerp_axis_angle


def _geodesic_angle(aa_a, aa_b) -> float:
    """Rotation angle (rad) between two axis-angle vectors."""
    qa, qb = aa_to_quat(np.array(aa_a)), aa_to_quat(np.array(aa_b))
    return 2.0 * math.acos(min(1.0, abs(float(np.dot(qa, qb)))))


# --- slerp math ---------------------------------------------------------------
def test_slerp_midpoint_is_half_rotation():
    a = np.array([[0.0, 0.0, 0.0]])               # identity
    b = np.array([[0.0, 0.0, math.pi / 2]])       # 90° about z
    mid = slerp_axis_angle(a, b, 0.5)[0]
    assert np.allclose(mid, [0.0, 0.0, math.pi / 4], atol=1e-6)  # 45° about z


# --- concatenation ------------------------------------------------------------
def test_concatenate_produces_valid_sequence():
    seq = concatenate([clip("A"), clip("B")], transition_frames=4)
    assert isinstance(seq, SMPLXSequence)
    assert seq.model == "SMPLX_NEUTRAL"
    # 2 frames + 4 transition + 2 frames
    assert len(seq.frames) == 2 + 4 + 2
    assert seq.meta.source_gloss == ["A", "B"]
    assert seq.meta.clip_ids == ["a-lexical", "b-lexical"]


def test_no_seam_discontinuity_above_threshold():
    # Internally-smooth clips (small per-frame steps), but a hard seam between
    # them: A ends at +1.2 rad, B starts at -1.2 rad (a ~2.4 rad jump). Slerp
    # transition frames must bridge that seam without a large per-step rotation.
    a = clip("A", frames=[frame(global_orient=(0.0, 0.0, z))
                          for z in np.linspace(0.0, 1.2, 8)])
    b = clip("B", frames=[frame(global_orient=(0.0, 0.0, z))
                          for z in np.linspace(-1.2, 0.0, 8)])

    blended = concatenate([a, b], transition_frames=8)
    raw = concatenate([a, b], transition_frames=0)

    def max_step(seq):
        gs = [f.global_orient for f in seq.frames]
        return max(_geodesic_angle(gs[i], gs[i + 1]) for i in range(len(gs) - 1))

    # the unblended boundary jumps ~2.4 rad; blending must keep steps small
    assert max_step(raw) > 1.5
    assert max_step(blended) < 0.5


def test_resample_changes_frame_count_to_target_fps():
    # 5 frames @ 60fps -> ~0.0667s -> resampled to 30fps -> fewer frames
    frames = [frame(global_orient=(0.0, 0.0, i * 0.1)) for i in range(5)]
    seq = concatenate([clip("A", frames=frames, fps=60.0)], fps=30.0)
    assert seq.fps == 30.0
    assert len(seq.frames) < 5


def test_rest_hold_inserts_frames():
    seq = concatenate([clip("A"), clip("B")], transition_frames=2, rest_hold_frames=3)
    # 2 + (3 hold + 2 transition) + 2
    assert len(seq.frames) == 2 + 3 + 2 + 2
