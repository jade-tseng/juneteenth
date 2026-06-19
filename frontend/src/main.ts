import "./styles.css";
import { Stage } from "./stage.ts";
import { Caption } from "./caption.ts";
import { Controls } from "./controls.ts";
import { SignPlayer } from "./player.ts";
import { DEMO_TIMELINE } from "./timeline.ts";
import type { SignSentence, SMPLXSequence } from "./types.ts";
import { tryStartVapi } from "./vapi.ts";

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

// Load the real SMPL-X mesh (Route A); when ready the player drives it instead
// of the placeholder rig. Failure logs and leaves the placeholder in place.
stage.loadSMPLX().then((mesh) => player.setMesh(mesh));

let state: State = "idle";
let listenTimer = 0;
let processTimer = 0;
let lastSentences: SignSentence[] = [];
let lastText = ""; // last phrase sent to the backend (for replay)

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
      // deterministic demo: sign the cached, hand-verified script (no backend)
      requestSigning();
      const f = Number(q.get("frame"));
      if (Number.isFinite(f) && f > 0) player.seek(f);
    }
  }
  player.update(dt);
});

// ── text input: the primary trigger (POST /api/sign) ───────────────────────
const textForm = document.getElementById("textform") as HTMLFormElement | null;
const textInput = document.getElementById("textinput") as HTMLInputElement | null;
textForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = (textInput?.value ?? "").trim();
  if (!text) return;
  requestSigningText(text);
});

// Vapi STT is scaffolded but gated behind creds (Phase 4). When unconfigured —
// the default in this build — typed text is the path; the mic mock stays.
tryStartVapi({
  onTranscript: (text) => requestSigningText(text),
  onListening: () => setState("listening"),
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

// Cached, hand-verified demo script (CLAUDE.md §5) — drives the placeholder
// gesture path for ?autoplay / the mic mock so the demo never depends on a live
// backend or LLM call. The real path is requestSigningText() below.
function requestSigning() {
  const sentences = DEMO_TIMELINE.sentences;
  lastSentences = sentences;
  lastText = "";
  startSigning(sentences);
}

// Real path: POST { text } to /api/sign on Cloud Run (via the Vite proxy in
// dev). 200 → render the returned SMPLXSequence on the SMPL-X mesh; 422 →
// unmatched-vocabulary UI; network/other errors → generic error copy. If the
// SMPL-X mesh hasn't loaded yet, fall back to the cached gesture demo.
async function requestSigningText(text: string) {
  lastText = text;
  lastSentences = [];
  setState("processing");
  try {
    const res = await fetch("/api/sign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (res.status === 422) {
      showUnmatched();
      return;
    }
    if (!res.ok) {
      showError();
      return;
    }
    const seq = (await res.json()) as SMPLXSequence;
    if (!stage.mesh || !seq.frames?.length) {
      // mesh not ready — fall back to the cached gesture demo so the UI works
      requestSigning();
      return;
    }
    setState("signing");
    player.playSMPLX(seq, controls.speedRate, () => setState("ready"));
  } catch {
    showError();
  }
}

function startSigning(sentences: SignSentence[]) {
  setState("signing");
  player.play(sentences, DEMO_TIMELINE.fps, controls.speedRate, () =>
    setState("ready")
  );
}

function replay() {
  if (lastText) {
    requestSigningText(lastText);
    return;
  }
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
