"""Shared fixture builders for the contract tests."""

from __future__ import annotations


def zero_frame() -> dict:
    """A structurally valid SMPLXFrame with all-zero (rest) pose."""
    return {
        "global_orient": [0.0, 0.0, 0.0],
        "body_pose": [0.0] * 63,
        "left_hand_pose": [0.0] * 45,
        "right_hand_pose": [0.0] * 45,
        "jaw_pose": [0.0, 0.0, 0.0],
        "leye_pose": [0.0, 0.0, 0.0],
        "reye_pose": [0.0, 0.0, 0.0],
        "expression": [0.0] * 10,
        "transl": [0.0, 0.0, 0.0],
    }


def valid_clip(gloss: str = "HELLO", kind: str = "lexical", n: int = 3) -> dict:
    return {
        "clip_id": f"{gloss.lower()}-001",
        "gloss": gloss,
        "kind": kind,
        "fps": 30.0,
        "betas": [0.0] * 10,
        "frames": [zero_frame() for _ in range(n)],
        "source": {"extractor": "SMPLer-X", "license": "CC-BY-NC"},
    }


def valid_sequence(n: int = 4) -> dict:
    return {
        "model": "SMPLX_NEUTRAL",
        "fps": 30.0,
        "betas": [0.0] * 10,
        "frames": [zero_frame() for _ in range(n)],
        "meta": {"source_gloss": ["HELLO"], "clip_ids": ["hello-001"]},
    }
