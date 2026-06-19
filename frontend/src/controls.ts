// Glass control bar (UI.md §11): mic (primary), replay, speed segment.
// Playback (replay + speed) is hidden until a phrase is ready.

const SPEEDS = [0.75, 1, 1.25] as const;

export interface ControlHandlers {
  onMic: () => void;
  onReplay: () => void;
  onSpeed: (rate: number) => void;
}

export class Controls {
  private dock = document.getElementById("dock")!;
  private mic = document.getElementById("mic") as HTMLButtonElement;
  private playback = document.getElementById("playback")!;
  private replay = document.getElementById("replay") as HTMLButtonElement;
  private speed = document.getElementById("speed")!;
  private rate = 1;

  constructor(private h: ControlHandlers) {
    this.mic.addEventListener("click", () => this.h.onMic());
    this.replay.addEventListener("click", () => this.h.onReplay());
    // Space/Enter on the mic is native button behaviour; keep it the focus
    // target on load so the primary action is one keypress away (§13).
    this.buildSpeed();
    this.mic.focus({ preventScroll: true });
  }

  private buildSpeed() {
    for (const s of SPEEDS) {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(s === this.rate));
      b.textContent = `${s}×`;
      b.addEventListener("click", () => {
        this.rate = s;
        for (const child of this.speed.children) {
          child.setAttribute(
            "aria-checked",
            String(child === b)
          );
        }
        this.h.onSpeed(s);
      });
      this.speed.appendChild(b);
    }
  }

  // ── mic state, mirrors §10 ────────────────────────────────────────────
  setListening(on: boolean) {
    this.mic.classList.toggle("listening", on);
    this.mic.setAttribute("aria-pressed", String(on));
    this.mic.setAttribute("aria-label", on ? "Listening" : "Tap to speak");
  }

  setProcessing(on: boolean) {
    this.dock.classList.toggle("processing", on);
  }

  showPlayback(on: boolean) {
    this.playback.hidden = !on;
  }

  setMicEnabled(on: boolean) {
    this.mic.disabled = !on;
  }

  get speedRate() {
    return this.rate;
  }
}
