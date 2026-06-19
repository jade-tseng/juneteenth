#!/usr/bin/env python3
"""Convert the official SMPL-X NEUTRAL .npz into a JS-loadable binary + header
for the Route A browser forward pass (CLAUDE.md §4.5).

We extract only what the in-browser forward pass needs and downcast to Float32
(except faces -> Int32). The body-only SMPL three.js demos load the same set;
this adds the SMPL-X hands + face channels.

Outputs (both gitignored, regenerate from the licensed model on disk):
  frontend/public/smplx/smplx_neutral.bin   concatenated little-endian typed arrays
  frontend/public/smplx/smplx_neutral.json  header: per-array dtype / shape / byteOffset / byteLength

Arrays packed (in this order):
  v_template   (N,3)        f32   template vertices                     (N≈10475)
  shapedirs    (N,3,10)     f32   first 10 shape blendshapes (betas)
  exprdirs     (N,3,10)     f32   first 10 expression blendshapes
  posedirs     (N,3,486)    f32   pose correctives (54 joints * 9)
  J_regressor  (55,N)       f32   joint regressor (dense)
  parents      (55,)        i32   kinematic-tree parent index (root = -1)
  lbs_weights  (N,55)       f32   linear-blend-skinning weights
  f            (F,3)        i32   triangle faces                        (F≈20908)

Layout / dim notes (validated below against the §3 schema):
  * SMPL-X has 55 joints. Pose vector = 165 = 55 joints * 3 (axis-angle).
    Order: global_orient(3) body_pose(63) jaw(3) leye(3) reye(3)
           left_hand(45) right_hand(45).
  * shapedirs in the npz is (N,3,400): [:300]=shape, [300:400]=expression.
    We keep the first 10 of each (schema: 10 betas, 10 expression).
  * posedirs is (N,3,486) = N,3,(54*9): the rotmat-minus-identity feature for
    the 54 non-root joints.
  * betas/expression length = 10 each per §3.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # assets/smplx -> repo root
MODEL = REPO / "models" / "smplx" / "SMPLX_NEUTRAL.npz"
OUT_DIR = REPO / "frontend" / "public" / "smplx"

N_BETAS = 10
N_EXPR = 10
N_JOINTS = 55
N_POSE = N_JOINTS * 3  # 165
N_POSEDIRS = (N_JOINTS - 1) * 9  # 486


def load_model(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"SMPL-X model not found at {path}. The licensed .npz lives on disk "
            "only (gitignored); place SMPLX_NEUTRAL.npz under models/smplx/."
        )
    d = np.load(path, allow_pickle=True)

    v_template = d["v_template"].astype(np.float32)            # (N,3)
    N = v_template.shape[0]

    shapedirs_all = d["shapedirs"].astype(np.float32)          # (N,3,400)
    shapedirs = np.ascontiguousarray(shapedirs_all[:, :, :N_BETAS])          # (N,3,10)
    exprdirs = np.ascontiguousarray(shapedirs_all[:, :, 300:300 + N_EXPR])   # (N,3,10)

    posedirs = np.ascontiguousarray(d["posedirs"].astype(np.float32))        # (N,3,486)
    J_regressor = np.ascontiguousarray(np.asarray(d["J_regressor"], dtype=np.float32))  # (55,N)
    lbs_weights = np.ascontiguousarray(d["weights"].astype(np.float32))      # (N,55)

    parents = d["kintree_table"][0].astype(np.int64).copy()    # (55,)
    parents[parents > 1_000_000] = -1                           # root sentinel (uint max) -> -1
    parents = parents.astype(np.int32)

    faces = np.ascontiguousarray(d["f"].astype(np.int32))      # (F,3)

    return {
        "N": N,
        "v_template": v_template,
        "shapedirs": shapedirs,
        "exprdirs": exprdirs,
        "posedirs": posedirs,
        "J_regressor": J_regressor,
        "parents": parents,
        "lbs_weights": lbs_weights,
        "f": faces,
    }


def validate(m: dict) -> None:
    N = m["N"]
    assert m["v_template"].shape == (N, 3), m["v_template"].shape
    assert m["shapedirs"].shape == (N, 3, N_BETAS), m["shapedirs"].shape
    assert m["exprdirs"].shape == (N, 3, N_EXPR), m["exprdirs"].shape
    assert m["posedirs"].shape == (N, 3, N_POSEDIRS), m["posedirs"].shape
    assert m["J_regressor"].shape == (N_JOINTS, N), m["J_regressor"].shape
    assert m["parents"].shape == (N_JOINTS,), m["parents"].shape
    assert m["lbs_weights"].shape == (N, N_JOINTS), m["lbs_weights"].shape
    assert m["f"].shape[1] == 3, m["f"].shape
    assert int(m["parents"][0]) == -1, "joint 0 (pelvis) must be the root"
    # schema cross-checks (§3): pose 165, betas 10, expr 10
    assert N_POSE == 165
    assert N_BETAS == 10 and N_EXPR == 10
    print(f"[validate] dims OK  N={N}  joints={N_JOINTS}  pose={N_POSE}  "
          f"betas={N_BETAS}  expr={N_EXPR}  faces={m['f'].shape[0]}")


def self_check(m: dict) -> None:
    """Numeric sanity: at zero pose + zero betas + zero expression the forward
    pass must return v_template. We re-implement the minimal forward pass here
    in numpy and compare against forward.ts behaviour (same math)."""
    N = m["N"]
    betas = np.zeros(N_BETAS, np.float32)
    expr = np.zeros(N_EXPR, np.float32)
    pose = np.zeros(N_POSE, np.float32)

    # v_shaped = template + shapedirs·betas + exprdirs·expr  (all zero -> template)
    v_shaped = (
        m["v_template"]
        + m["shapedirs"].reshape(N * 3, N_BETAS).dot(betas).reshape(N, 3)
        + m["exprdirs"].reshape(N * 3, N_EXPR).dot(expr).reshape(N, 3)
    )

    # pose feature for the 54 non-root joints: (R(theta_j) - I) flattened row-major
    feat = np.zeros(N_POSEDIRS, np.float32)
    for j in range(1, N_JOINTS):
        aa = pose[3 * j:3 * j + 3]
        R = aa_to_matrix(aa)
        feat[(j - 1) * 9:(j - 1) * 9 + 9] = (R - np.eye(3)).reshape(9)
    v_posed = v_shaped + m["posedirs"].reshape(N * 3, N_POSEDIRS).dot(feat).reshape(N, 3)

    # forward kinematics: all rotations identity -> global transforms are pure
    # translations to each rest joint, so LBS leaves vertices at v_posed.
    J = m["J_regressor"].dot(v_shaped)  # (55,3)
    parents = m["parents"]
    A = np.zeros((N_JOINTS, 4, 4), np.float32)
    for j in range(N_JOINTS):
        T = np.eye(4, dtype=np.float32)
        T[:3, :3] = aa_to_matrix(pose[3 * j:3 * j + 3])
        if parents[j] < 0:
            T[:3, 3] = J[j]
            A[j] = T
        else:
            T[:3, 3] = J[j] - J[parents[j]]
            A[j] = A[parents[j]].dot(T)
    # relative transform that maps rest -> posed (subtract rest-joint offset)
    A_rel = A.copy()
    for j in range(N_JOINTS):
        off = A[j][:3, :3].dot(J[j])
        A_rel[j][:3, 3] = A[j][:3, 3] - off

    W = m["lbs_weights"]                       # (N,55)
    Tv = np.einsum("nj,jkl->nkl", W, A_rel)    # (N,4,4)
    vh = np.concatenate([v_posed, np.ones((N, 1), np.float32)], axis=1)  # (N,4)
    out = np.einsum("nkl,nl->nk", Tv, vh)[:, :3]

    err = np.abs(out - m["v_template"]).max()
    finite = np.isfinite(out).all() and np.isfinite(J).all()
    print(f"[self-check] zero-pose max |out - v_template| = {err:.3e}  finite={finite}")
    assert finite, "non-finite vertices/joints at zero pose"
    assert err < 1e-4, f"zero-pose output should equal v_template, got max err {err}"
    print("[self-check] PASS")


def aa_to_matrix(aa: np.ndarray) -> np.ndarray:
    """Rodrigues: axis-angle (3,) -> rotation matrix (3,3). Mirrors forward.ts."""
    theta = float(np.linalg.norm(aa))
    if theta < 1e-8:
        return np.eye(3, dtype=np.float32)
    k = aa / theta
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]], np.float32)
    return (np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * K.dot(K)).astype(np.float32)


def pack(m: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # order matters: keep header in sync with the bin layout
    arrays = [
        ("v_template", m["v_template"], "f32"),
        ("shapedirs", m["shapedirs"], "f32"),
        ("exprdirs", m["exprdirs"], "f32"),
        ("posedirs", m["posedirs"], "f32"),
        ("J_regressor", m["J_regressor"], "f32"),
        ("parents", m["parents"], "i32"),
        ("lbs_weights", m["lbs_weights"], "f32"),
        ("f", m["f"], "i32"),
    ]

    header = {
        "model": "SMPLX_NEUTRAL",
        "N": int(m["N"]),
        "n_joints": N_JOINTS,
        "n_betas": N_BETAS,
        "n_expr": N_EXPR,
        "n_pose": N_POSE,
        "n_posedirs": N_POSEDIRS,
        "arrays": [],
    }

    bin_path = OUT_DIR / "smplx_neutral.bin"
    json_path = OUT_DIR / "smplx_neutral.json"

    offset = 0
    with bin_path.open("wb") as fh:
        for name, arr, dtype in arrays:
            np_dtype = np.float32 if dtype == "f32" else np.int32
            buf = np.ascontiguousarray(arr, dtype=np_dtype)
            # little-endian on disk; JS DataView reads will assume LE
            data = buf.astype(f"<{ 'f4' if dtype == 'f32' else 'i4' }").tobytes()
            fh.write(data)
            header["arrays"].append({
                "name": name,
                "dtype": dtype,
                "shape": list(buf.shape),
                "byteOffset": offset,
                "byteLength": len(data),
            })
            offset += len(data)

    with json_path.open("w") as fh:
        json.dump(header, fh, indent=2)

    print(f"[pack] wrote {bin_path}  ({offset / 1e6:.1f} MB)")
    print(f"[pack] wrote {json_path}")


def main() -> None:
    print(f"[load] {MODEL}")
    m = load_model(MODEL)
    validate(m)
    self_check(m)
    pack(m)
    print("[done] conversion complete")


if __name__ == "__main__":
    main()
