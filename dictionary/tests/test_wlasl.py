"""WLASL selection logic — tested against a small inline fixture (no download)."""
from __future__ import annotations

import json

from aslpipe.wlasl import (
    SEED_LEXICAL,
    clip_id_for,
    select_for_seed,
    select_instance,
    write_selection,
)


def _inst(video_id, split, frame_start=1, frame_end=60, signer_id=1, instance_id=0):
    return {
        "video_id": video_id, "split": split,
        "frame_start": frame_start, "frame_end": frame_end,
        "signer_id": signer_id, "instance_id": instance_id,
        "url": f"http://example.com/{video_id}.mp4",
    }


def _fixture_metadata():
    """One entry per seed gloss except COMMUNICATE (covered via its synonym
    'talk'); a few entries carry instances designed to exercise the policy."""
    md = []
    for g in SEED_LEXICAL:
        if g == "COMMUNICATE":
            continue
        md.append({"gloss": g.lower(), "instances": [_inst(f"{g.lower()}_vid", "train")]})
    # COMMUNICATE -> synonym 'talk'
    md.append({"gloss": "talk", "instances": [_inst("talk_vid", "train")]})
    return md


def test_clip_id_matches_manifest_convention():
    assert clip_id_for("HELLO") == "hello-001"
    assert clip_id_for("COMMUNICATE") == "communicate-001"


def test_select_instance_prefers_non_test_split():
    entry = {"gloss": "hello", "instances": [
        _inst("v_test", "test"),
        _inst("v_train", "train"),
        _inst("v_val", "val"),
    ]}
    assert select_instance(entry)["video_id"] == "v_train"


def test_select_instance_prefers_reasonable_length():
    # same split: a 50-frame clip beats a 5-frame (too short) and 500 (too long).
    entry = {"gloss": "hello", "instances": [
        _inst("v_short", "train", frame_start=1, frame_end=6),
        _inst("v_good", "train", frame_start=1, frame_end=51),
        _inst("v_long", "train", frame_start=1, frame_end=501),
    ]}
    assert select_instance(entry)["video_id"] == "v_good"


def test_select_instance_tiebreak_is_stable():
    entry = {"gloss": "hello", "instances": [
        _inst("v_b", "train", signer_id=5, instance_id=2),
        _inst("v_a", "train", signer_id=2, instance_id=1),
    ]}
    # lower signer_id wins the tie -> deterministic
    assert select_instance(entry)["video_id"] == "v_a"


def test_select_for_seed_covers_12_directly_and_communicate_via_synonym():
    sel = select_for_seed(_fixture_metadata())
    by_gloss = {s["gloss"]: s for s in sel["selections"]}
    # all 13 seed lexical glosses resolved, nothing missing
    assert sel["missing"] == []
    assert set(by_gloss) == set(SEED_LEXICAL)
    # COMMUNICATE resolved through the synonym 'talk'
    comm = by_gloss["COMMUNICATE"]
    assert comm["clip_id"] == "communicate-001"
    assert comm["wlasl_gloss"] == "talk"
    assert comm["synonym_of"] == "talk"
    assert comm["video_id"] == "talk_vid"
    # a direct hit carries no synonym marker
    assert "synonym_of" not in by_gloss["HELLO"]


def test_missing_gloss_reported():
    # drop 'talk' so COMMUNICATE has no candidate
    md = [e for e in _fixture_metadata() if e["gloss"] != "talk"]
    sel = select_for_seed(md)
    assert sel["missing"] == ["COMMUNICATE"]
    assert all(s["gloss"] != "COMMUNICATE" for s in sel["selections"])


def test_write_selection_roundtrips(tmp_path):
    sel = select_for_seed(_fixture_metadata())
    out = write_selection(sel, tmp_path / "wlasl_selection.json")
    loaded = json.loads(out.read_text())
    assert loaded["selections"] and "missing" in loaded
