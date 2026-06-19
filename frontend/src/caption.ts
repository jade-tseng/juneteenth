// The caption that breathes (UI.md §7, §12 — the signature). Two modes:
//   • status line — quiet prompts ("Listening…", errors)
//   • sentence    — the words being signed, revealed one-by-one in sync with
//                   the avatar's clock (§14: caption and figure share one clock)

export class Caption {
  private words: HTMLElement[] = [];
  private revealed = -1;

  constructor(private el: HTMLElement) {}

  /** A single quiet line (idle prompt, listening/translating, error). */
  status(text: string, kind: "prompt" | "error" = "prompt") {
    this.el.className = kind;
    this.el.replaceChildren();
    this.words = [];
    this.revealed = -1;
    const span = document.createElement("span");
    span.className = "word";
    span.textContent = text;
    this.el.appendChild(span);
    requestAnimationFrame(() => span.classList.add("in"));
  }

  /** Lay out a full sentence dimmed; reveal() lights words as signing reaches them. */
  sentence(text: string, wordTexts: string[]) {
    this.el.className = "";
    this.el.setAttribute("aria-label", text);
    this.el.replaceChildren();
    this.words = wordTexts.map((w, i) => {
      const span = document.createElement("span");
      span.className = "word pending";
      span.textContent = i === wordTexts.length - 1 ? w : w + " ";
      this.el.appendChild(span);
      return span;
    });
    this.revealed = -1;
  }

  /** Reveal words 0..index with the blur→sharp crossfade. Idempotent. */
  reveal(index: number) {
    if (index <= this.revealed) return;
    for (let i = this.revealed + 1; i <= index && i < this.words.length; i++) {
      const w = this.words[i];
      w.classList.remove("pending");
      // next frame so the transition runs from the pending state
      requestAnimationFrame(() => w.classList.add("in"));
    }
    this.revealed = Math.min(index, this.words.length - 1);
  }

  clear() {
    this.el.className = "";
    this.el.replaceChildren();
    this.words = [];
    this.revealed = -1;
  }
}
