"""WLASL gloss-metadata parsing + per-gloss video selection (real-clip path).

WLASL (Word-Level ASL, https://github.com/dxli94/WLASL) ships a metadata file
`WLASL_v0.3.json`: a list of entries, one per gloss, each with a list of video
`instances`. We do NOT download the videos here (third-party hosting, large,
some dead links) — this module only reads the metadata and decides, for each
target seed gloss (§5), which single video instance to extract.

Selection policy (best-effort, deterministic):
  * prefer non-`test` split (train > val > test) — test videos are held out and
    sometimes the worst quality;
  * prefer a "reasonable length" clip (frame_end - frame_start) — not too short
    (clipped sign) nor too long (slow/repeated);
  * tie-break on signer_id / instance_id for stable output.

Output: gloss -> clip_id (`{gloss_lower}-001`, matching manifest.json) plus the
chosen video_id / url / split, emitted as a JSON selection manifest. That
manifest is the input to the SMPLer-X extraction path (build.py extract):
download exactly those video_ids, extract, clean, build, upload.

COMMUNICATE is absent from WLASL; we resolve it to a synonym (TALK) — see
SYNONYMS below and dictionary/REAL_CLIPS.md.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Optional

# §5 seed lexical glosses. Fingerspelling (J/A/D/E/I) is descoped for v1, so the
# WLASL path only covers the 13 lexical words.
SEED_LEXICAL = [
    "HELLO", "HOW", "YOU", "TODAY", "MY", "NAME", "ME", "SIGN", "NOT", "BUT",
    "CAN", "HAPPY", "COMMUNICATE",
]

# COMMUNICATE is not a WLASL gloss. Map seed glosses to the WLASL gloss to look
# up. The clip_id keeps the seed gloss (so W3 lookup still resolves COMMUNICATE),
# but the source video is the synonym's. Order = preference; first one present
# in the metadata wins.
SYNONYMS: dict[str, list[str]] = {
    "COMMUNICATE": ["communicate", "talk", "communication", "interact"],
}

# WLASL upstream metadata (start_kit). Fetch the JSON only — never the videos.
WLASL_METADATA_URL = (
    "https://raw.githubusercontent.com/dxli94/WLASL/master/start_kit/WLASL_v0.3.json"
)

# split preference: lower rank = preferred.
_SPLIT_RANK = {"train": 0, "val": 1, "test": 2}

# A "reasonable" sign length window in frames (WLASL videos are ~25fps). Outside
# this window an instance is penalised, not excluded.
_GOOD_LEN_LO = 20
_GOOD_LEN_HI = 120


def clip_id_for(gloss: str) -> str:
    """`{gloss_lower}-001`, matching manifest.json's clip_ids."""
    return f"{gloss.lower()}-001"


def load_metadata(path: Optional[Path] = None) -> list[dict]:
    """Load WLASL_v0.3.json from a local path, or fetch it from upstream.

    Pass an explicit `path` in offline/CI use. With no path it downloads the
    metadata JSON (small) from `WLASL_METADATA_URL`. Never downloads videos.
    """
    if path is not None:
        return json.loads(Path(path).read_text())
    with urllib.request.urlopen(WLASL_METADATA_URL) as resp:  # noqa: S310 (trusted upstream)
        return json.loads(resp.read().decode("utf-8"))


def _instance_length(inst: dict) -> Optional[int]:
    """Frame count of an instance, or None if unknown (frame_end == -1)."""
    start = inst.get("frame_start", 1)
    end = inst.get("frame_end", -1)
    if end is None or end < 0:
        return None
    return max(0, end - start)


def _instance_sort_key(inst: dict) -> tuple:
    """Lower is better. Prefer non-test split, then a reasonable length, then a
    stable tie-break on signer/instance id."""
    split = inst.get("split", "test")
    split_rank = _SPLIT_RANK.get(split, 3)

    length = _instance_length(inst)
    if length is None:
        len_penalty = 2  # unknown length: worse than good, better than out-of-range
    elif _GOOD_LEN_LO <= length <= _GOOD_LEN_HI:
        len_penalty = 0
    else:
        len_penalty = 1

    signer = inst.get("signer_id", 1 << 30)
    instance_id = inst.get("instance_id", 1 << 30)
    return (split_rank, len_penalty, signer, instance_id)


def select_instance(entry: dict) -> Optional[dict]:
    """Pick the single preferred instance for one WLASL gloss entry."""
    instances = entry.get("instances") or []
    if not instances:
        return None
    return min(instances, key=_instance_sort_key)


def _index_by_gloss(metadata: list[dict]) -> dict[str, dict]:
    return {entry.get("gloss", "").lower(): entry for entry in metadata}


def select_for_seed(metadata: list[dict]) -> dict:
    """Build the selection manifest for the §5 seed lexical vocabulary.

    Returns:
      {
        "selections": [ {gloss, clip_id, wlasl_gloss, video_id, url, split,
                         frame_start, frame_end, synonym_of?}, ... ],
        "missing":    [ gloss, ... ]   # no WLASL gloss + no synonym present
      }
    """
    by_gloss = _index_by_gloss(metadata)
    selections: list[dict] = []
    missing: list[str] = []

    for gloss in SEED_LEXICAL:
        # candidate WLASL glosses: the gloss itself, then any synonyms.
        candidates = [gloss.lower()] + SYNONYMS.get(gloss, [])
        chosen_entry = None
        chosen_wlasl = None
        for cand in candidates:
            entry = by_gloss.get(cand)
            if entry and (entry.get("instances")):
                chosen_entry = entry
                chosen_wlasl = cand
                break
        if chosen_entry is None:
            missing.append(gloss)
            continue

        inst = select_instance(chosen_entry)
        if inst is None:
            missing.append(gloss)
            continue

        sel = {
            "gloss": gloss,
            "clip_id": clip_id_for(gloss),
            "wlasl_gloss": chosen_wlasl,
            "video_id": inst.get("video_id"),
            "url": inst.get("url"),
            "split": inst.get("split"),
            "frame_start": inst.get("frame_start"),
            "frame_end": inst.get("frame_end"),
        }
        if chosen_wlasl != gloss.lower():
            sel["synonym_of"] = chosen_wlasl  # COMMUNICATE -> talk, etc.
        selections.append(sel)

    return {"selections": selections, "missing": missing}


def write_selection(selection: dict, out_path: Path) -> Path:
    """Write the selection manifest as pretty JSON."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(selection, indent=2) + "\n")
    return out_path
