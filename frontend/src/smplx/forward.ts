// SMPL-X forward pass (Route A, CLAUDE.md §4.5), CPU / typed-array.
//
//   v_shaped = v_template + shapedirs·betas + exprdirs·expression
//   feat_j   = R(theta_j) - I   for the 54 non-root joints (row-major 3x3)
//   v_posed  = v_shaped + posedirs·feat
//   J        = J_regressor·v_shaped
//   FK over `parents` -> 55 global 4x4 transforms; subtract rest-joint offset
//   v_out    = sum_j  w[v,j] * A_rel[j] * v_posed[v]    (linear blend skinning)
//
// Full pose vector order (165) assembled from SMPLXFrame fields:
//   global_orient(3) body_pose(63) jaw_pose(3) leye_pose(3) reye_pose(3)
//   left_hand_pose(45) right_hand_pose(45)
// which maps 1:1 onto SMPL-X joints 0..54 (pelvis, body 1..21, jaw 22, leye 23,
// reye 24, left hand 25..39, right hand 40..54).
//
// betas are constant per sequence, so the shape term is folded into v_template
// once via bindBetas(); per-frame work is expression + pose only.

import type { SMPLXModel } from "./model.ts";
import type { SMPLXFrame } from "../types.ts";

export class SMPLXForward {
  private m: SMPLXModel;
  private N: number;
  private J: number; // joints

  // v_shaped with betas folded in (shape is constant for a sequence)
  private vShapedBase: Float32Array; // (N*3)
  // scratch buffers, allocated once
  private vShaped: Float32Array; // (N*3) base + expression
  private vPosed: Float32Array; // (N*3)
  private out: Float32Array; // (N*3) final vertices
  private joints: Float32Array; // (J*3)
  private feat: Float32Array; // (nPosedirs)
  private rot: Float32Array; // (J*9) per-joint local rotation matrices
  private global: Float32Array; // (J*16) global 4x4 (column-... see note)
  private relRot: Float32Array; // (J*9) global rotation part
  private relT: Float32Array; // (J*3) translation part of A_rel

  constructor(model: SMPLXModel) {
    this.m = model;
    this.N = model.N;
    this.J = model.nJoints;
    const N3 = this.N * 3;
    this.vShapedBase = new Float32Array(N3);
    this.vShaped = new Float32Array(N3);
    this.vPosed = new Float32Array(N3);
    this.out = new Float32Array(N3);
    this.joints = new Float32Array(this.J * 3);
    this.feat = new Float32Array(model.nPosedirs);
    this.rot = new Float32Array(this.J * 9);
    this.global = new Float32Array(this.J * 16);
    this.relRot = new Float32Array(this.J * 9);
    this.relT = new Float32Array(this.J * 3);
    // default to zero betas until bindBetas() is called
    this.vShapedBase.set(model.vTemplate);
  }

  /** Fold a sequence's constant betas into the shape base (call once per seq). */
  bindBetas(betas: number[]): void {
    const m = this.m;
    const N3 = this.N * 3;
    const K = m.nBetas;
    this.vShapedBase.set(m.vTemplate);
    const sd = m.shapedirs; // row-major [v*3 + c][k]
    for (let i = 0; i < N3; i++) {
      let acc = 0;
      const o = i * K;
      for (let k = 0; k < K; k++) acc += sd[o + k] * (betas[k] ?? 0);
      this.vShapedBase[i] += acc;
    }
  }

  /** Run the full forward pass for one frame; returns the internal output
   *  buffer (do not retain across calls — copy if you need to keep it). */
  compute(frame: SMPLXFrame): Float32Array {
    const pose = assemblePose(frame);
    this.applyExpression(frame.expression ?? []);
    this.applyPose(pose);
    this.skin();
    return this.out;
  }

  /** Convenience: forward pass for the canonical rest/neutral pose. */
  computeRest(): Float32Array {
    const pose = new Float32Array(this.m.nPose);
    this.vShaped.set(this.vShapedBase); // no expression
    this.applyPoseFromArray(pose);
    this.skin();
    return this.out;
  }

  // ── expression: vShaped = base + exprdirs·expression ─────────────────────
  private applyExpression(expr: number[]): void {
    const m = this.m;
    const N3 = this.N * 3;
    const K = m.nExpr;
    this.vShaped.set(this.vShapedBase);
    const ed = m.exprdirs;
    for (let i = 0; i < N3; i++) {
      let acc = 0;
      const o = i * K;
      for (let k = 0; k < K; k++) acc += ed[o + k] * (expr[k] ?? 0);
      this.vShaped[i] += acc;
    }
  }

  private applyPose(pose: Float32Array): void {
    this.applyPoseFromArray(pose);
  }

  // ── pose: local rotations, posedirs correctives, FK ──────────────────────
  private applyPoseFromArray(pose: Float32Array): void {
    const m = this.m;
    const J = this.J;

    // per-joint local rotation matrices (Rodrigues)
    for (let j = 0; j < J; j++) {
      aaToMat(pose, j * 3, this.rot, j * 9);
    }

    // pose feature (R - I) for the 54 non-root joints, row-major
    const feat = this.feat;
    for (let j = 1; j < J; j++) {
      const ro = j * 9;
      const fo = (j - 1) * 9;
      feat[fo + 0] = this.rot[ro + 0] - 1;
      feat[fo + 1] = this.rot[ro + 1];
      feat[fo + 2] = this.rot[ro + 2];
      feat[fo + 3] = this.rot[ro + 3];
      feat[fo + 4] = this.rot[ro + 4] - 1;
      feat[fo + 5] = this.rot[ro + 5];
      feat[fo + 6] = this.rot[ro + 6];
      feat[fo + 7] = this.rot[ro + 7];
      feat[fo + 8] = this.rot[ro + 8] - 1;
    }

    // v_posed = v_shaped + posedirs·feat
    const N3 = this.N * 3;
    const P = m.nPosedirs;
    const pd = m.posedirs; // row-major [v*3 + c][p]
    for (let i = 0; i < N3; i++) {
      let acc = 0;
      const o = i * P;
      for (let p = 0; p < P; p++) acc += pd[o + p] * feat[p];
      this.vPosed[i] = this.vShaped[i] + acc;
    }

    // joints from the *shaped* (not posed) verts: J = J_regressor · v_shaped
    this.regressJoints();
    // forward kinematics -> global transforms + rest-relative transforms
    this.forwardKinematics(pose);
  }

  private regressJoints(): void {
    const m = this.m;
    const N = this.N;
    const J = this.J;
    const jr = m.jRegressor; // (J*N) row-major
    const v = this.vShaped;
    for (let j = 0; j < J; j++) {
      let x = 0,
        y = 0,
        z = 0;
      const row = j * N;
      for (let n = 0; n < N; n++) {
        const w = jr[row + n];
        if (w === 0) continue;
        const vo = n * 3;
        x += w * v[vo];
        y += w * v[vo + 1];
        z += w * v[vo + 2];
      }
      const o = j * 3;
      this.joints[o] = x;
      this.joints[o + 1] = y;
      this.joints[o + 2] = z;
    }
  }

  private forwardKinematics(_pose: Float32Array): void {
    const J = this.J;
    const parents = this.m.parents;
    const Jp = this.joints;
    const rot = this.rot;
    const G = this.global; // 4x4 row-major per joint

    for (let j = 0; j < J; j++) {
      const ro = j * 9;
      const go = j * 16;
      const p = parents[j];
      // local transform L: rotation rot[j], translation = J[j] - J[parent]
      let tx = Jp[j * 3],
        ty = Jp[j * 3 + 1],
        tz = Jp[j * 3 + 2];
      if (p >= 0) {
        tx -= Jp[p * 3];
        ty -= Jp[p * 3 + 1];
        tz -= Jp[p * 3 + 2];
      }
      if (p < 0) {
        // root: global = local
        mat4FromRotT(rot, ro, tx, ty, tz, G, go);
      } else {
        // global = G[parent] * L
        mul4x4WithRotT(G, p * 16, rot, ro, tx, ty, tz, G, go);
      }
    }

    // rest-relative: A_rel = G with translation adjusted to subtract R·J_rest,
    // so a vertex at its rest position maps to itself when all rotations are I.
    const relRot = this.relRot;
    const relT = this.relT;
    for (let j = 0; j < J; j++) {
      const go = j * 16;
      const ro = j * 9;
      // copy 3x3 rotation
      relRot[ro + 0] = G[go + 0];
      relRot[ro + 1] = G[go + 1];
      relRot[ro + 2] = G[go + 2];
      relRot[ro + 3] = G[go + 4];
      relRot[ro + 4] = G[go + 5];
      relRot[ro + 5] = G[go + 6];
      relRot[ro + 6] = G[go + 8];
      relRot[ro + 7] = G[go + 9];
      relRot[ro + 8] = G[go + 10];
      const jx = Jp[j * 3],
        jy = Jp[j * 3 + 1],
        jz = Jp[j * 3 + 2];
      // offset = R · J_rest
      const ox = relRot[ro + 0] * jx + relRot[ro + 1] * jy + relRot[ro + 2] * jz;
      const oy = relRot[ro + 3] * jx + relRot[ro + 4] * jy + relRot[ro + 5] * jz;
      const oz = relRot[ro + 6] * jx + relRot[ro + 7] * jy + relRot[ro + 8] * jz;
      relT[j * 3] = G[go + 3] - ox;
      relT[j * 3 + 1] = G[go + 7] - oy;
      relT[j * 3 + 2] = G[go + 11] - oz;
    }
  }

  // ── linear blend skinning ────────────────────────────────────────────────
  private skin(): void {
    const N = this.N;
    const J = this.J;
    const W = this.m.lbsWeights; // (N*J)
    const relRot = this.relRot;
    const relT = this.relT;
    const vp = this.vPosed;
    const out = this.out;

    for (let n = 0; n < N; n++) {
      const vo = n * 3;
      const vx = vp[vo],
        vy = vp[vo + 1],
        vz = vp[vo + 2];
      const wrow = n * J;
      let ox = 0,
        oy = 0,
        oz = 0;
      for (let j = 0; j < J; j++) {
        const w = W[wrow + j];
        if (w === 0) continue;
        const ro = j * 9;
        const to = j * 3;
        // (R·v + t) accumulated by weight
        const rx = relRot[ro + 0] * vx + relRot[ro + 1] * vy + relRot[ro + 2] * vz + relT[to];
        const ry = relRot[ro + 3] * vx + relRot[ro + 4] * vy + relRot[ro + 5] * vz + relT[to + 1];
        const rz = relRot[ro + 6] * vx + relRot[ro + 7] * vy + relRot[ro + 8] * vz + relT[to + 2];
        ox += w * rx;
        oy += w * ry;
        oz += w * rz;
      }
      out[vo] = ox;
      out[vo + 1] = oy;
      out[vo + 2] = oz;
    }
  }
}

// ── pose assembly ───────────────────────────────────────────────────────────
// Assemble the 165-vector in SMPL-X joint order from the §3.1 frame fields.
const POSE_LEN = 165;

export function assemblePose(frame: SMPLXFrame): Float32Array {
  const p = new Float32Array(POSE_LEN);
  let o = 0;
  o = copyInto(p, o, frame.global_orient, 3);
  o = copyInto(p, o, frame.body_pose, 63);
  o = copyInto(p, o, frame.jaw_pose, 3);
  o = copyInto(p, o, frame.leye_pose, 3);
  o = copyInto(p, o, frame.reye_pose, 3);
  o = copyInto(p, o, frame.left_hand_pose, 45);
  o = copyInto(p, o, frame.right_hand_pose, 45);
  return p; // o === 165
}

function copyInto(dst: Float32Array, off: number, src: number[] | undefined, len: number): number {
  if (src) for (let i = 0; i < len; i++) dst[off + i] = src[i] ?? 0;
  return off + len;
}

// ── math helpers ─────────────────────────────────────────────────────────────
// Rodrigues: axis-angle at pose[po..po+2] -> 3x3 row-major into rot[ro..ro+8].
function aaToMat(pose: ArrayLike<number>, po: number, rot: Float32Array, ro: number): void {
  const ax = pose[po],
    ay = pose[po + 1],
    az = pose[po + 2];
  const theta = Math.sqrt(ax * ax + ay * ay + az * az);
  if (theta < 1e-8) {
    rot[ro + 0] = 1; rot[ro + 1] = 0; rot[ro + 2] = 0;
    rot[ro + 3] = 0; rot[ro + 4] = 1; rot[ro + 5] = 0;
    rot[ro + 6] = 0; rot[ro + 7] = 0; rot[ro + 8] = 1;
    return;
  }
  const kx = ax / theta,
    ky = ay / theta,
    kz = az / theta;
  const s = Math.sin(theta);
  const c = Math.cos(theta);
  const t = 1 - c;
  // R = I + s·K + t·K², K = skew(k)
  rot[ro + 0] = t * kx * kx + c;
  rot[ro + 1] = t * kx * ky - s * kz;
  rot[ro + 2] = t * kx * kz + s * ky;
  rot[ro + 3] = t * kx * ky + s * kz;
  rot[ro + 4] = t * ky * ky + c;
  rot[ro + 5] = t * ky * kz - s * kx;
  rot[ro + 6] = t * kx * kz - s * ky;
  rot[ro + 7] = t * ky * kz + s * kx;
  rot[ro + 8] = t * kz * kz + c;
}

// 4x4 (row-major) from a 3x3 rotation + translation.
function mat4FromRotT(
  rot: Float32Array,
  ro: number,
  tx: number,
  ty: number,
  tz: number,
  out: Float32Array,
  o: number
): void {
  out[o + 0] = rot[ro + 0]; out[o + 1] = rot[ro + 1]; out[o + 2] = rot[ro + 2]; out[o + 3] = tx;
  out[o + 4] = rot[ro + 3]; out[o + 5] = rot[ro + 4]; out[o + 6] = rot[ro + 5]; out[o + 7] = ty;
  out[o + 8] = rot[ro + 6]; out[o + 9] = rot[ro + 7]; out[o + 10] = rot[ro + 8]; out[o + 11] = tz;
  out[o + 12] = 0; out[o + 13] = 0; out[o + 14] = 0; out[o + 15] = 1;
}

// out = P (4x4 at po) * L, where L = [rot | t]. Row-major.
function mul4x4WithRotT(
  P: Float32Array,
  po: number,
  rot: Float32Array,
  ro: number,
  tx: number,
  ty: number,
  tz: number,
  out: Float32Array,
  o: number
): void {
  // L columns: 0..2 = rotation cols, 3 = translation. P is 4x4.
  for (let r = 0; r < 3; r++) {
    const p0 = P[po + r * 4 + 0];
    const p1 = P[po + r * 4 + 1];
    const p2 = P[po + r * 4 + 2];
    const p3 = P[po + r * 4 + 3];
    // column 0
    out[o + r * 4 + 0] = p0 * rot[ro + 0] + p1 * rot[ro + 3] + p2 * rot[ro + 6];
    // column 1
    out[o + r * 4 + 1] = p0 * rot[ro + 1] + p1 * rot[ro + 4] + p2 * rot[ro + 7];
    // column 2
    out[o + r * 4 + 2] = p0 * rot[ro + 2] + p1 * rot[ro + 5] + p2 * rot[ro + 8];
    // column 3 = P·[t;1]
    out[o + r * 4 + 3] = p0 * tx + p1 * ty + p2 * tz + p3;
  }
  out[o + 12] = 0; out[o + 13] = 0; out[o + 14] = 0; out[o + 15] = 1;
}
