// Forward-pass sanity check for the TS implementation (mirrors the numpy
// self-check in assets/smplx/convert.py). Loads the converted bin from disk and
// verifies that at zero pose + zero betas + zero expression the forward pass
// returns v_template (within float tolerance) and all outputs are finite.
//
// Run with:  npx tsx src/smplx/check.ts   (from frontend/, after convert.py)
// This is a dev/CI numeric check, not shipped in the bundle.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type { SMPLXModel, SMPLXHeader, SMPLXHeaderArray } from "./model.ts";
import { SMPLXForward } from "./forward.ts";
import type { SMPLXFrame } from "../types.ts";

const here = dirname(fileURLToPath(import.meta.url));
const dir = resolve(here, "../../public/smplx");

function loadFromDisk(): SMPLXModel {
  const header = JSON.parse(
    readFileSync(resolve(dir, "smplx_neutral.json"), "utf8")
  ) as SMPLXHeader;
  const raw = readFileSync(resolve(dir, "smplx_neutral.bin"));
  // copy into a clean ArrayBuffer (node Buffer may be a pooled slice)
  const buf = raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);

  const pick = (name: string): SMPLXHeaderArray => {
    const a = header.arrays.find((x) => x.name === name);
    if (!a) throw new Error(`missing array ${name}`);
    return a;
  };
  const f32 = (n: string) => {
    const a = pick(n);
    return new Float32Array(buf, a.byteOffset, a.byteLength / 4);
  };
  const i32 = (n: string) => {
    const a = pick(n);
    return new Int32Array(buf, a.byteOffset, a.byteLength / 4);
  };
  return {
    N: header.N,
    nJoints: header.n_joints,
    nBetas: header.n_betas,
    nExpr: header.n_expr,
    nPose: header.n_pose,
    nPosedirs: header.n_posedirs,
    vTemplate: f32("v_template"),
    shapedirs: f32("shapedirs"),
    exprdirs: f32("exprdirs"),
    posedirs: f32("posedirs"),
    jRegressor: f32("J_regressor"),
    parents: i32("parents"),
    lbsWeights: f32("lbs_weights"),
    faces: Uint32Array.from(i32("f")),
  };
}

function zeroFrame(): SMPLXFrame {
  const z = (n: number) => new Array(n).fill(0);
  return {
    global_orient: z(3),
    body_pose: z(63),
    left_hand_pose: z(45),
    right_hand_pose: z(45),
    jaw_pose: z(3),
    leye_pose: z(3),
    reye_pose: z(3),
    expression: z(10),
    transl: z(3),
  };
}

function main() {
  const model = loadFromDisk();
  const fwd = new SMPLXForward(model);
  fwd.bindBetas(new Array(model.nBetas).fill(0));

  // compute() returns the forward pass's reused internal buffer, so copy each
  // result before running the next frame (otherwise they alias).
  const out = Float32Array.from(fwd.compute(zeroFrame()));

  let maxErr = 0;
  let finite = true;
  const t = model.vTemplate;
  for (let i = 0; i < out.length; i++) {
    if (!Number.isFinite(out[i])) finite = false;
    const e = Math.abs(out[i] - t[i]);
    if (e > maxErr) maxErr = e;
  }

  // a non-trivial pose must move vertices and stay finite
  const f2 = zeroFrame();
  f2.right_hand_pose = f2.right_hand_pose.map((_, i) => (i % 3 === 2 ? 0.8 : 0));
  f2.body_pose[16 * 3 + 2] = -0.9; // bend the right shoulder
  const out2 = Float32Array.from(fwd.compute(f2));
  let moved = 0;
  let finite2 = true;
  for (let i = 0; i < out2.length; i++) {
    if (!Number.isFinite(out2[i])) finite2 = false;
    if (Math.abs(out2[i] - out[i]) > 1e-3) moved++;
  }

  console.log(`[ts-check] N=${model.N} joints=${model.nJoints}`);
  console.log(`[ts-check] zero-pose max |out - v_template| = ${maxErr.toExponential(3)}  finite=${finite}`);
  console.log(`[ts-check] posed-frame vertices moved = ${moved}  finite=${finite2}`);

  const ok = finite && finite2 && maxErr < 1e-4 && moved > 1000;
  if (!ok) {
    console.error("[ts-check] FAIL");
    process.exit(1);
  }
  console.log("[ts-check] PASS");
}

main();
