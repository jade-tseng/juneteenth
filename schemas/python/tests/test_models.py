"""Contract tests — these are what 'CI rejects malformed clips' (W0) means."""

from __future__ import annotations

import json

import pytest
from conftest import valid_clip, valid_sequence, zero_frame
from pydantic import ValidationError

from asl_schemas import GlossSequence, SMPLXClip, SMPLXFrame, SMPLXSequence
from asl_schemas.validate import validate_file


# --- happy paths --------------------------------------------------------------
def test_valid_clip_roundtrips():
    clip = SMPLXClip.model_validate(valid_clip())
    again = SMPLXClip.model_validate(json.loads(clip.model_dump_json()))
    assert again == clip


def test_valid_sequence():
    seq = SMPLXSequence.model_validate(valid_sequence())
    assert seq.model == "SMPLX_NEUTRAL" and len(seq.frames) == 4


def test_optional_pose_fields_zero_fill():
    f = zero_frame()
    del f["leye_pose"], f["reye_pose"], f["transl"]
    frame = SMPLXFrame.model_validate(f)
    assert frame.leye_pose == [0.0, 0.0, 0.0]
    assert frame.transl == [0.0, 0.0, 0.0]


def test_gloss_sequence_with_fingerspell():
    g = GlossSequence.model_validate(
        {"english": "my name is jade", "gloss": ["MY", "NAME", "fs:J", "fs:A"]}
    )
    assert g.gloss[2] == "fs:J"


# --- the rejections that matter -----------------------------------------------
@pytest.mark.parametrize(
    "field,bad_len",
    [
        ("body_pose", 62),
        ("left_hand_pose", 44),   # PCA / truncated hand must be rejected
        ("right_hand_pose", 46),
        ("expression", 9),
        ("global_orient", 2),
    ],
)
def test_wrong_dimension_rejected(field, bad_len):
    f = zero_frame()
    f[field] = [0.0] * bad_len
    with pytest.raises(ValidationError):
        SMPLXFrame.model_validate(f)


def test_wrong_betas_length_rejected():
    bad = valid_clip()
    bad["betas"] = [0.0] * 11
    with pytest.raises(ValidationError):
        SMPLXClip.model_validate(bad)


def test_extra_field_forbidden():
    bad = valid_clip()
    bad["surprise"] = True
    with pytest.raises(ValidationError):
        SMPLXClip.model_validate(bad)


def test_bad_kind_rejected():
    bad = valid_clip()
    bad["kind"] = "lexicall"
    with pytest.raises(ValidationError):
        SMPLXClip.model_validate(bad)


def test_empty_frames_rejected():
    bad = valid_clip(n=0)
    with pytest.raises(ValidationError):
        SMPLXClip.model_validate(bad)


def test_non_positive_fps_rejected():
    bad = valid_clip()
    bad["fps"] = 0
    with pytest.raises(ValidationError):
        SMPLXClip.model_validate(bad)


# --- CLI validator on real files ----------------------------------------------
def test_validate_file_ok(tmp_path):
    p = tmp_path / "clip.json"
    p.write_text(json.dumps(valid_clip()))
    assert validate_file(p, "clip") == []


def test_validate_file_reports_errors(tmp_path):
    bad = valid_clip()
    bad["frames"][0]["left_hand_pose"] = [0.0] * 44
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    errors = validate_file(p, "clip")
    assert errors and "left_hand_pose" in errors[0]


def test_validate_file_auto_infers_clip(tmp_path):
    p = tmp_path / "clip.json"
    p.write_text(json.dumps(valid_clip()))
    assert validate_file(p, "auto") == []
