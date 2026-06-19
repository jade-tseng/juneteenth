import type { Avatar } from "./avatar.ts";
import type { Caption } from "./caption.ts";
import type { GestureCue, SignSentence } from "./types.ts";

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

  constructor(private avatar: Avatar, private caption: Caption) {}

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

  setSpeed(speed: number) {
    this.speed = speed;
  }

  stop() {
    this.playing = false;
    this.avatar.settleToRest();
  }

  update(dt: number) {
    if (!this.playing) return;
    this.cursor += dt * this.fps * this.speed;

    if (this.cursor >= this.total) {
      this.playing = false;
      this.avatar.settleToRest();
      this.onEnd?.();
      return;
    }
    this.applyCurrent();
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
