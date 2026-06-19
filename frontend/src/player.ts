import type { Avatar } from "./avatar.ts";
import type { Caption } from "./caption.ts";
import type { SMPLXMesh } from "./smplx/mesh.ts";
import type { GestureCue, SignSentence, SMPLXSequence } from "./types.ts";

// Drives the avatar and the caption from a single frame cursor (UI.md §14).
// A schedule of timed steps is built once from the timeline; update(dt) walks
// the cursor forward at fps × speed, switching the caption per sentence and
// revealing words as the avatar reaches them. When real SMPL-X frames exist
// this same cursor indexes SMPLXSequence.frames instead of gesture cues.

interface Step {
  sentenceIdx: number;
  wordIdx: number; // -1 during lead-in / rest holds (no new reveal)
  gesture: GestureCue;
  start: number; // absolute frame
  end: number;
}

const LEAD_IN = 8; // frames before the first sign (keeps time-to-first-sign low)
const REST_HOLD = 16; // frames of stillness between sentences

type Mode = "gesture" | "smplx";

export class SignPlayer {
  private steps: Step[] = [];
  private fps = 30;
  private sentences: SignSentence[] = [];
  private cursor = 0;
  private total = 0;
  private speed = 1;
  private playing = false;
  private lastSentence = -1;
  private lastWord = -1;
  private onEnd?: () => void;

  // ── SMPL-X playback (real frames from POST /api/sign) ──────────────────────
  private mode: Mode = "gesture";
  private mesh: SMPLXMesh | null = null;
  private seq: SMPLXSequence | null = null;
  private spanRevealed = -1; // last caption word index revealed in smplx mode
  private captionWords: string[] = []; // the user's spoken words shown as caption

  constructor(private avatar: Avatar, private caption: Caption) {}

  /** Bind the real SMPL-X mesh once the stage finishes loading it. */
  setMesh(mesh: SMPLXMesh | null) {
    this.mesh = mesh;
  }

  private build(sentences: SignSentence[]) {
    const steps: Step[] = [];
    let f = 0;
    // lead-in: caption for sentence 0 appears, nothing revealed yet
    steps.push({ sentenceIdx: 0, wordIdx: -1, gesture: "rest", start: 0, end: LEAD_IN });
    f = LEAD_IN;

    sentences.forEach((sentence, si) => {
      sentence.words.forEach((word, wi) => {
        const per = word.frames / word.gestures.length;
        word.gestures.forEach((g, gi) => {
          const start = f + per * gi;
          steps.push({
            sentenceIdx: si,
            wordIdx: wi,
            gesture: g,
            start,
            end: start + per,
          });
        });
        f += word.frames;
      });
      // rest hold between sentences — caption of the finished sentence stays
      steps.push({ sentenceIdx: si, wordIdx: -1, gesture: "rest", start: f, end: f + REST_HOLD });
      f += REST_HOLD;
    });

    this.steps = steps;
    this.total = f;
  }

  play(sentences: SignSentence[], fps: number, speed: number, onEnd?: () => void) {
    this.mode = "gesture";
    this.sentences = sentences;
    this.fps = fps;
    this.speed = speed;
    this.onEnd = onEnd;
    this.build(sentences);
    this.cursor = 0;
    this.lastSentence = -1;
    this.lastWord = -1;
    this.playing = true;
  }

  /**
   * Play a real SMPL-X sequence from POST /api/sign on the loaded mesh. The
   * cursor advances at seq.fps × speed; each frame is rendered via mesh.setFrame.
   * Caption words are revealed using meta.clip_frame_spans (each word lights
   * during its clip's [start,end) span) when present, evenly otherwise (§14).
   * Falls back to no-op if the mesh has not loaded.
   */
  playSMPLX(
    seq: SMPLXSequence,
    speed: number,
    captionText: string,
    onEnd?: () => void
  ) {
    if (!this.mesh || !seq.frames.length) {
      onEnd?.();
      return;
    }
    this.mode = "smplx";
    this.seq = seq;
    this.fps = seq.fps || 30;
    this.speed = speed;
    this.onEnd = onEnd;
    this.cursor = 0;
    this.total = seq.frames.length;
    this.spanRevealed = -1;

    this.mesh.bindBetas(seq.betas ?? []);

    // The caption shows the user's spoken words — NOT the gloss/default. When the
    // word count happens to match the clips, words light per clip span; otherwise
    // they reveal evenly across the sequence (revealSpansUpTo).
    const words = captionText.trim() ? captionText.trim().split(/\s+/) : [];
    this.captionWords = words;
    if (words.length) {
      this.caption.sentence(words.join(" "), words);
    } else {
      this.caption.clear();
    }
    this.mesh.setFrame(seq.frames[0]);
    this.playing = true;
  }

  setSpeed(speed: number) {
    this.speed = speed;
  }

  stop() {
    this.playing = false;
    if (this.mode === "smplx") this.mesh?.setRest();
    else this.avatar.settleToRest();
  }

  update(dt: number) {
    if (!this.playing) return;
    this.cursor += dt * this.fps * this.speed;

    if (this.mode === "smplx") {
      this.updateSMPLX();
      return;
    }

    if (this.cursor >= this.total) {
      this.playing = false;
      this.avatar.settleToRest();
      this.onEnd?.();
      return;
    }
    this.applyCurrent();
  }

  private updateSMPLX() {
    const seq = this.seq;
    if (!seq || !this.mesh) return;

    if (this.cursor >= this.total) {
      // reveal any remaining words and settle to rest
      this.revealSpansUpTo(this.total);
      this.playing = false;
      this.mesh.setRest();
      this.onEnd?.();
      return;
    }

    const frame = Math.floor(this.cursor);
    this.mesh.setFrame(seq.frames[frame]);
    this.revealSpansUpTo(frame);
  }

  /** Reveal each caption word whose clip span has started by `frame` (§14). */
  private revealSpansUpTo(frame: number) {
    const spans = this.seq?.meta?.clip_frame_spans;
    const words = this.captionWords;
    if (!words.length) return;
    if (spans && spans.length === words.length) {
      // light each word once its clip's [start,end) span has begun
      for (let i = this.spanRevealed + 1; i < words.length; i++) {
        if (frame >= spans[i][0]) {
          this.caption.reveal(i);
          this.spanRevealed = i;
        } else break;
      }
    } else {
      // no spans: distribute words evenly across the sequence
      const idx = Math.min(
        words.length - 1,
        Math.floor((frame / Math.max(1, this.total)) * words.length)
      );
      if (idx > this.spanRevealed) {
        this.caption.reveal(idx);
        this.spanRevealed = idx;
      }
    }
  }

  /** Jump the cursor to a frame and render that moment (debug / scrubbing). */
  seek(frame: number) {
    this.cursor = Math.max(0, Math.min(frame, this.total - 1));
    this.lastSentence = -1;
    this.lastWord = -1;
    this.applyCurrent();
  }

  private applyCurrent() {
    const step = this.stepAt(this.cursor);
    if (!step) return;

    // reveal every word up to the cursor (so a seek fills the line correctly)
    if (step.sentenceIdx !== this.lastSentence) {
      const s = this.sentences[step.sentenceIdx];
      this.caption.sentence(s.english, s.words.map((w) => w.text));
      this.lastSentence = step.sentenceIdx;
      this.lastWord = -1;
    }
    if (step.wordIdx >= 0 && step.wordIdx !== this.lastWord) {
      this.caption.reveal(step.wordIdx);
      this.lastWord = step.wordIdx;
    }
    this.avatar.applyGesture(step.gesture);
  }

  private stepAt(frame: number): Step | undefined {
    // small lists; linear scan is fine and keeps the cursor authoritative
    for (const s of this.steps) {
      if (frame >= s.start && frame < s.end) return s;
    }
    return this.steps[this.steps.length - 1];
  }
}
