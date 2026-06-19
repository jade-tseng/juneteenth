"""SMPLer-X extraction wrapper — the real W6 path (runs on the GPU VM).

This shells out to a SMPLer-X (OSX-class) inference run over a single reference
video and parses its per-frame SMPL-X parameter dump into posekit.Frame objects.
SMPLer-X is heavy (CUDA, model checkpoints) and is provisioned only on the GPU
VM (see gpu_vm/), so this module imports cleanly without it and fails loudly
only when actually invoked without the estimator present.

Output contract from SMPLer-X varies by fork; we expect a per-frame dump of:
  global_orient[3], body_pose[63], left_hand_pose[45], right_hand_pose[45],
  jaw_pose[3], expression[10]  (+ optional leye/reye/transl)
as .npz or .json. Adjust _parse_dump() to match the checkpoint you run.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

from .posekit import BODY_DIM, EXPR_DIM, HAND_DIM, Frame

# Path to a SMPLer-X inference entrypoint, set on the GPU VM (see gpu_vm/setup.sh).
SMPLERX_INFER = os.environ.get("SMPLERX_INFER", "")


def extract_video(video_path: Path, work_dir: Path) -> list[Frame]:
    """Run SMPLer-X on one video and return raw per-frame SMPL-X params.

    The result is *unclean* — feed it through clean.clean_frames() before
    building a clip.
    """
    if not SMPLERX_INFER:
        raise RuntimeError(
            "SMPLERX_INFER is unset — real extraction runs only on the GPU VM. "
            "Use `python build.py synth` for placeholder clips off-GPU."
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    # Convention: the inference script writes one params file per frame into
    # work_dir/params/. Flags differ per fork; keep them in one place.
    subprocess.run(
        ["python", SMPLERX_INFER,
         "--video", str(video_path),
         "--out", str(work_dir),
         "--save_params", "--full_hand_pose"],  # full 45-dim hands, NOT PCA
        check=True,
    )
    return _load_param_dir(work_dir / "params")


def _load_param_dir(params_dir: Path) -> list[Frame]:
    files = sorted(params_dir.glob("*.npz")) or sorted(params_dir.glob("*.json"))
    if not files:
        raise RuntimeError(f"no per-frame params found in {params_dir}")
    return [_parse_dump(f) for f in files]


def _parse_dump(path: Path) -> Frame:
    data = np.load(path) if path.suffix == ".npz" else json.loads(path.read_text())

    def vec(key: str, n: int) -> np.ndarray:
        if key not in data:
            return np.zeros(n)
        return np.asarray(data[key], dtype=float).reshape(-1)[:n]

    return Frame(
        global_orient=vec("global_orient", 3),
        body_pose=vec("body_pose", BODY_DIM),
        left_hand_pose=vec("left_hand_pose", HAND_DIM),
        right_hand_pose=vec("right_hand_pose", HAND_DIM),
        jaw_pose=vec("jaw_pose", 3),
        leye_pose=vec("leye_pose", 3),
        reye_pose=vec("reye_pose", 3),
        expression=vec("expression", EXPR_DIM),
        transl=vec("transl", 3),
    )
