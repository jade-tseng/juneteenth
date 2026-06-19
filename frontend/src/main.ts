import "./styles.css";
import { Stage } from "./stage.ts";
import { Caption } from "./caption.ts";
import { Controls } from "./controls.ts";
import { SignPlayer } from "./player.ts";
import { DEMO_TIMELINE } from "./timeline.ts";
import type { SignSentence } from "./types.ts";

// signspace — Voice-to-ASL Signing Avatar (POC), frontend entry point.
// Wires the luminous stage, the breathing caption, the glass controls, and a
// small state machine (UI.md §10). STT (Vapi → POST /api/sign, W1/API) is not
// wired here; the mic runs a faithful mock pipeline and plays the pre-verified
// cached demo script (CLAUDE.md §5) so the experience is demonstrable today.
// Swap requestSigning() to call the real backend once it lands.

type State = "idle" | "listening" | "processing" | "signing" | "ready" | "error";

const canvas = document.getElementById("stage") as HTMLCanvasElement;
const captionEl = document.getElementById("caption")!;
const wordmark = document.getElementById("wordmark")!;

const stage = new Stage(canvas);
const caption = new Caption(captionEl);
const player = new SignPlayer(stage.avatar, caption);

let state: State = "idle";
let listenTimer = 0;
let processTimer = 0;
let lastSentences: SignSentence[] = [];

const controls = new Controls({
  onMic: () => onMic(),
  onReplay: () => replay(),
  onSpeed: (rate) => player.setSpeed(rate),
});

// ── boot: show the calm loader until the first frame is on screen (§11) ──
wordmark.classList.add("loading");
let booted = false;
stage.start((dt) => {
  if (!booted) {
    booted = true;
    wordmark.classList.remove("loading");
    setState("idle");
    // ?autoplay — skip the mic and sign the cached script (demo / screenshots)
    // ?frame=N — autoplay then seek to a frame (deterministic for testing)
    const q = new URLSearchParams(location.search);
    if (q.has("autoplay") || q.has("frame")) {
      requestSigning();
      const f = Number(q.get("frame"));
      if (Number.isFinite(f) && f > 0) player.seek(f);
    }
  }
  player.update(dt);
});

// ── state machine (§10) ──────────────────────────────────────────────────
function setState(next: State) {
  state = next;
  window.clearTimeout(listenTimer);
  window.clearTimeout(processTimer);

  switch (next) {
    case "idle":
      controls.setListening(false);
      controls.setProcessing(false);
      caption.status("Tap to speak");
      break;

    case "listening":
      controls.setListening(true);
      controls.setProcessing(false);
      controls.showPlayback(false);
      caption.status("Listening…");
      // simulate end-of-utterance detection (Vapi would emit the transcript)
      listenTimer = window.setTimeout(() => setState("processing"), 1600);
      break;

    case "processing":
      controls.setListening(false);
      controls.setProcessing(true);
      caption.status("Translating…");
      // simulate gloss + lookup + blend round-trip, then sign the result
      processTimer = window.setTimeout(() => requestSigning(), 850);
      break;

    case "signing":
      controls.setProcessing(false);
      controls.showPlayback(true);
      break;

    case "ready":
      // phrase finished; replay + speed stay available, mic ready again
      controls.setListening(false);
      controls.setProcessing(false);
      break;

    case "error":
      controls.setListening(false);
      controls.setProcessing(false);
      break;
  }
}

function onMic() {
  switch (state) {
    case "idle":
    case "ready":
    case "error":
      setState("listening");
      break;
    case "listening":
      // tapping again "sends" early
      setState("processing");
      break;
    case "signing":
    case "processing":
      // interrupt and listen again
      player.stop();
      setState("listening");
      break;
  }
}

// Resolve speech → signs. Today: the cached, hand-verified demo script.
// Later: POST { text } to /api/sign on Cloud Run, render the returned
// SMPLXSequence, and surface 422 (unmatched vocabulary) via showUnmatched().
function requestSigning() {
  const sentences = DEMO_TIMELINE.sentences;
  lastSentences = sentences;
  startSigning(sentences);
}

function startSigning(sentences: SignSentence[]) {
  setState("signing");
  player.play(sentences, DEMO_TIMELINE.fps, controls.speedRate, () =>
    setState("ready")
  );
}

function replay() {
  if (!lastSentences.length) return;
  startSigning(lastSentences);
}

// Error copy per §10 — actionable, never an apology. Wired for the backend
// path: call on network failure; showUnmatched() on a 422 from /api/sign.
export function showError() {
  setState("error");
  caption.status("Didn't catch that — tap to try again.", "error");
}
export function showUnmatched() {
  setState("error");
  caption.status("I don't know those signs yet.", "error");
}
void showError;
void showUnmatched;
