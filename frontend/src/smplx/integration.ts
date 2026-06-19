// End-to-end integration check: real backend /api/sign response -> the SMPL-X
// forward pass. Proves the renderer can consume what the API actually returns
// (multi-clip blended sequence from GCS clips), not just a synthetic frame.
//
// Run with:  BASE=http://127.0.0.1:8080 npx tsx src/smplx/integration.ts
// Requires: the backend running on $BASE, and convert.py already run.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type { SMPLXModel, SMPLXHeader, SMPLXHeaderArray } from "./model.ts";
import { SMPLXForward } from "./forward.ts";
import type { SMPLXSequence } from "../types.ts";

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const here = dirname(fileURLToPath(import.meta.url));
const dir = resolve(here, "../../public/smplx");

function loadFromDisk(): SMPLXModel {
  const header = JSON.parse(
    readFileSync(resolve(dir, "smplx_neutral.json"), "utf8")
  ) as SMPLXHeader;
  const raw = readFileSync(resolve(dir, "smplx_neutral.bin"));
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
    N: header.N, nJoints: header.n_joints, nBetas: header.n_betas,
    nExpr: header.n_expr, nPose: header.n_pose, nPosedirs: header.n_posedirs,
    vTemplate: f32("v_template"), shapedirs: f32("shapedirs"),
    exprdirs: f32("exprdirs"), posedirs: f32("posedirs"),
    jRegressor: f32("J_regressor"), parents: i32("parents"),
    lbsWeights: f32("lbs_weights"), faces: Uint32Array.from(i32("f")),
  };
}

async function main() {
  // 1. Real API call
  const text = "I can sign.";
  const res = await fetch(`${BASE}/api/sign`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`/api/sign -> ${res.status}`);
  const seq = (await res.json()) as SMPLXSequence;
  console.log(`[int] "${text}" -> ${seq.frames.length} frames @ ${seq.fps}fps`);
  console.log(`[int] clip_ids=${JSON.stringify(seq.meta?.clip_ids)}`);
  console.log(`[int] clip_frame_spans=${JSON.stringify(seq.meta?.clip_frame_spans)}`);

  // 2. Drive the forward pass with every returned frame
  const model = loadFromDisk();
  const fwd = new SMPLXForward(model);
  fwd.bindBetas(seq.betas ?? new Array(model.nBetas).fill(0));

  let prev: Float32Array | null = null;
  let allFinite = true;
  let movingFrames = 0;
  for (const frame of seq.frames) {
    const verts = Float32Array.from(fwd.compute(frame));
    if (verts.length !== model.N * 3) throw new Error("vertex count mismatch");
    for (let i = 0; i < verts.length; i++) {
      if (!Number.isFinite(verts[i])) { allFinite = false; break; }
    }
    if (prev) {
      let moved = 0;
      for (let i = 0; i < verts.length; i++) if (Math.abs(verts[i] - prev[i]) > 1e-3) moved++;
      if (moved > 100) movingFrames++;
    }
    prev = verts;
  }

  // 3. Assertions: real frames render, hands actually move across the sequence
  const spans = seq.meta?.clip_frame_spans ?? [];
  const spansAligned = spans.length === (seq.meta?.clip_ids?.length ?? -1);
  const ok = allFinite && movingFrames > 5 && seq.frames.length > 30 && spansAligned;
  console.log(`[int] finite=${allFinite}  moving_frames=${movingFrames}/${seq.frames.length - 1}  spans_aligned=${spansAligned}`);
  if (!ok) { console.error("[int] FAIL"); process.exit(1); }
  console.log("[int] PASS — backend sequence renders through the SMPL-X forward pass");
}

main().catch((e) => { console.error("[int] ERROR", e); process.exit(1); });
