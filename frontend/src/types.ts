// Frozen data contracts — mirror of CLAUDE.md §3. The schemas package (W0)
// is the eventual source of truth; these are the typed interfaces the frontend
// consumes from POST /api/sign so the player can be wired in directly later.

export interface SMPLXFrame {
  global_orient: number[]; // [3]
  body_pose: number[]; // [63] 21 body joints * 3
  left_hand_pose: number[]; // [45] 15 finger joints * 3 (full, not PCA)
  right_hand_pose: number[]; // [45]
  jaw_pose: number[]; // [3]
  leye_pose: number[]; // [3]
  reye_pose: number[]; // [3]
  expression: number[]; // [10]
  transl: number[]; // [3]
}

export interface SMPLXSequence {
  model: "SMPLX_NEUTRAL";
  fps: number;
  betas: number[]; // [10]
  frames: SMPLXFrame[];
  meta?: { source_gloss?: string[]; clip_ids?: string[] };
}

// ── Caption/avatar timing ───────────────────────────────────────────────
// §14: the caption advances from the sequence's own clock — fps + per-clip
// frame counts map elapsed frames → current word. Until the real SMPL-X player
// (renderer-agent, Route A) and dictionary clips (W6) exist, the placeholder
// avatar consumes this same SignTimeline so the caption and figure share one
// clock now and stay in sync when real frames replace the gesture cues.

export interface SignWord {
  /** What the caption shows, e.g. "My" or "Jade". One English word. */
  text: string;
  /** Gloss tokens this word maps to, e.g. ["NAME"] or ["fs:J","fs:A",…]. */
  gloss: string[];
  /** Frames this word occupies in the sequence (drives caption timing). */
  frames: number;
  /** Gesture(s) the placeholder avatar steps through across `frames`. */
  gestures: GestureCue[];
}

/** Sentence = a run of words plus the original English for the live caption. */
export interface SignSentence {
  english: string;
  words: SignWord[];
}

export interface SignTimeline {
  fps: number;
  sentences: SignSentence[];
}

// Procedural cue the placeholder avatar performs per token. Each is a
// hand/arm target the rig eases toward; this is intentionally not SMPL-X —
// it is honest scaffolding that the renderer-agent's forward pass replaces.
export type GestureCue =
  | "rest"
  | "wave" // HELLO
  | "point-out" // YOU
  | "point-self" // ME / MY
  | "two-hands-up" // HOW / question
  | "tap-down" // TODAY / NOT
  | "name-tap" // NAME (H-hands tap)
  | "sign-sweep" // SIGN
  | "but" // BUT
  | "can" // CAN
  | "happy" // HAPPY (chest brush)
  | "communicate" // COMMUNICATE (alternating C)
  | "fingerspell"; // any fs:<letter>
