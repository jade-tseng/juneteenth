// SMPL-X model assets loader (Route A, CLAUDE.md §4.5).
// Fetches the binary blob + JSON header produced by assets/smplx/convert.py and
// hands back plain typed-array views the forward pass reads directly. The bin is
// served from frontend/public/smplx/ in dev and from the smplx-model GCS bucket
// in prod (§7); both are reachable at the same relative URL because vite base="./".

export interface SMPLXHeaderArray {
  name: string;
  dtype: "f32" | "i32";
  shape: number[];
  byteOffset: number;
  byteLength: number;
}

export interface SMPLXHeader {
  model: string;
  N: number;
  n_joints: number;
  n_betas: number;
  n_expr: number;
  n_pose: number;
  n_posedirs: number;
  arrays: SMPLXHeaderArray[];
}

export interface SMPLXModel {
  N: number; // vertex count (≈10475)
  nJoints: number; // 55
  nBetas: number; // 10
  nExpr: number; // 10
  nPose: number; // 165
  nPosedirs: number; // 486

  vTemplate: Float32Array; // (N*3)
  shapedirs: Float32Array; // (N*3*nBetas) row-major [v][xyz][k]
  exprdirs: Float32Array; // (N*3*nExpr)
  posedirs: Float32Array; // (N*3*nPosedirs)
  jRegressor: Float32Array; // (nJoints*N)
  parents: Int32Array; // (nJoints) root = -1
  lbsWeights: Float32Array; // (N*nJoints)
  faces: Uint32Array; // (F*3)
}

// Default to the bundled dev path; in prod set VITE_SMPLX_BASE to the public
// smplx-model GCS URL (§7) so the 65MB assets aren't shipped with the bundle.
const BASE = import.meta.env.VITE_SMPLX_BASE ?? "./smplx";

export async function loadSMPLXModel(base = BASE): Promise<SMPLXModel> {
  const [header, buf] = await Promise.all([
    fetch(`${base}/smplx_neutral.json`).then((r) => {
      if (!r.ok) throw new Error(`SMPL-X header HTTP ${r.status}`);
      return r.json() as Promise<SMPLXHeader>;
    }),
    fetch(`${base}/smplx_neutral.bin`).then((r) => {
      if (!r.ok) throw new Error(`SMPL-X binary HTTP ${r.status}`);
      return r.arrayBuffer();
    }),
  ]);

  const pick = (name: string): SMPLXHeaderArray => {
    const a = header.arrays.find((x) => x.name === name);
    if (!a) throw new Error(`SMPL-X header missing array "${name}"`);
    return a;
  };

  const f32 = (name: string): Float32Array => {
    const a = pick(name);
    return new Float32Array(buf, a.byteOffset, a.byteLength / 4);
  };
  const i32 = (name: string): Int32Array => {
    const a = pick(name);
    return new Int32Array(buf, a.byteOffset, a.byteLength / 4);
  };

  const facesI32 = i32("f");

  const model: SMPLXModel = {
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
    // BufferGeometry index wants an unsigned int array
    faces: Uint32Array.from(facesI32),
  };
  return model;
}
