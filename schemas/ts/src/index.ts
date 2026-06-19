/**
 * Frozen §3 data contracts for the Voice-to-ASL Signing Avatar POC.
 *
 * Hand-mirrored from schemas/python/asl_schemas/models.py (the source of
 * truth). Keep in sync; the canonical JSON Schema in schemas/json/ is generated
 * from the same models. Rotations are axis-angle, radians. `betas` is constant
 * per sequence/clip.
 *
 * TypeScript can't enforce tuple length at runtime, so the dims are documented
 * and checked via the helpers below + the Python validator in CI.
 */

// Fixed-length vectors (lengths enforced by the Python validator / JSON Schema).
export type Vec3 = [number, number, number];
export type BodyPose = number[]; // length 63 (21 body joints * 3)
export type HandPose = number[]; // length 45 (15 finger joints * 3, full NOT PCA)
export type Expression = number[]; // length 10
export type Betas = number[]; // length 10

/** §3.1 */
export interface SMPLXFrame {
  global_orient: Vec3;
  body_pose: BodyPose;
  left_hand_pose: HandPose;
  right_hand_pose: HandPose;
  jaw_pose: Vec3;
  leye_pose: Vec3; // optional upstream, zero-filled on serialize
  reye_pose: Vec3; // optional upstream, zero-filled on serialize
  expression: Expression;
  transl: Vec3; // optional upstream, zero-filled on serialize
}

export interface SMPLXSequenceMeta {
  source_gloss?: string[];
  clip_ids?: string[];
}

/** §3.1 */
export interface SMPLXSequence {
  model: "SMPLX_NEUTRAL";
  fps: number;
  betas: Betas;
  frames: SMPLXFrame[];
  meta?: SMPLXSequenceMeta;
}

export interface SMPLXClipSource {
  video_url?: string;
  license?: string;
  extractor?: string;
}

/** §3.2 */
export interface SMPLXClip {
  clip_id: string;
  gloss: string; // lexical gloss OR single letter for fingerspell
  kind: "lexical" | "letter";
  fps: number;
  betas: Betas;
  frames: SMPLXFrame[]; // trimmed, rest-pose padded ends
  source?: SMPLXClipSource;
}

/** §3.3 — tokens are a lexical gloss ("HELLO") or fingerspell ("fs:J"). */
export interface GlossSequence {
  english: string;
  gloss: string[];
  unmatched?: string[];
}

/** §3.4 */
export interface VapiTranscriptWebhook {
  type: "transcript";
  transcript: string;
  timestamp: number;
}

/** §3.5 */
export interface SignRequest {
  text: string;
}
export interface SignError {
  error: string;
  unmatched: string[];
}

// --- Expected vector dimensions, for runtime sanity checks in the player. -----
export const DIMS = {
  global_orient: 3,
  body_pose: 63,
  left_hand_pose: 45,
  right_hand_pose: 45,
  jaw_pose: 3,
  leye_pose: 3,
  reye_pose: 3,
  expression: 10,
  betas: 10,
  transl: 3,
} as const;

const ZERO3: Vec3 = [0, 0, 0];

/**
 * Throw if a frame's vectors are the wrong length. Cheap guard for the renderer
 * (W5) so a malformed sequence fails loud instead of producing garbage poses.
 */
export function assertFrameDims(frame: SMPLXFrame): void {
  const checks: [keyof typeof DIMS, number[]][] = [
    ["global_orient", frame.global_orient],
    ["body_pose", frame.body_pose],
    ["left_hand_pose", frame.left_hand_pose],
    ["right_hand_pose", frame.right_hand_pose],
    ["jaw_pose", frame.jaw_pose],
    ["expression", frame.expression],
  ];
  for (const [name, vec] of checks) {
    if (vec?.length !== DIMS[name]) {
      throw new Error(`SMPLXFrame.${name}: expected ${DIMS[name]}, got ${vec?.length}`);
    }
  }
}

/** Fill optional pose fields so the renderer always sees complete frames. */
export function withDefaults(frame: SMPLXFrame): SMPLXFrame {
  return {
    ...frame,
    leye_pose: frame.leye_pose ?? [...ZERO3],
    reye_pose: frame.reye_pose ?? [...ZERO3],
    transl: frame.transl ?? [...ZERO3],
  };
}
