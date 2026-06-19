// Vapi STT (CLAUDE.md §4.1, W1). Wires the @vapi-ai/web SDK so the mic does live
// speech→text: start a call, surface the user's interim + final transcripts, and
// mute the assistant so it never talks back (STT only — no TTS, §1a/§4.1).
//
// Gated behind creds: the Web SDK needs a PUBLIC key + an assistant id
// (VITE_VAPI_PUBLIC_KEY / VITE_VAPI_ASSISTANT_ID, injected at build time — both
// are client-safe). When either is absent, vapiConfigured() is false and main.ts
// keeps the typed-text + mock path instead.

import Vapi from "@vapi-ai/web";

interface VapiEnv {
  VITE_VAPI_PUBLIC_KEY?: string;
  VITE_VAPI_ASSISTANT_ID?: string;
}

function readEnv(): VapiEnv {
  // import.meta.env is statically replaced by Vite at build time.
  const env = import.meta.env as unknown as VapiEnv;
  return {
    VITE_VAPI_PUBLIC_KEY: env.VITE_VAPI_PUBLIC_KEY,
    VITE_VAPI_ASSISTANT_ID: env.VITE_VAPI_ASSISTANT_ID,
  };
}

export function vapiConfigured(): boolean {
  const { VITE_VAPI_PUBLIC_KEY, VITE_VAPI_ASSISTANT_ID } = readEnv();
  return Boolean(VITE_VAPI_PUBLIC_KEY && VITE_VAPI_ASSISTANT_ID);
}

export interface VapiHandlers {
  /** Call connected, mic open. */
  onListening?: () => void;
  /** Live interim transcript — updates as the user speaks. */
  onPartial?: (text: string) => void;
  /** Final user utterance — drive the signing pipeline with this. */
  onFinal: (text: string) => void;
  /** Call ended (user stopped, or after a final utterance). */
  onEnd?: () => void;
  /** SDK / connection error. */
  onError?: (error: unknown) => void;
}

/**
 * Start/stop controller around a single Vapi call. The mic button drives it:
 * start() opens the call, stop() ends it. The instance is reused across calls.
 */
export class VapiSTT {
  private vapi: Vapi | null = null;
  private running = false;

  constructor(private h: VapiHandlers) {}

  get isRunning(): boolean {
    return this.running;
  }

  /** Start a call. Returns false (no-op) when creds are absent or start fails. */
  async start(): Promise<boolean> {
    const { VITE_VAPI_PUBLIC_KEY, VITE_VAPI_ASSISTANT_ID } = readEnv();
    if (!VITE_VAPI_PUBLIC_KEY || !VITE_VAPI_ASSISTANT_ID) return false;
    if (this.running) return true;

    if (!this.vapi) {
      const vapi = new Vapi(VITE_VAPI_PUBLIC_KEY);
      vapi.on("call-start", () => {
        // STT only: silence the assistant so the mic just transcribes (§4.1).
        try {
          vapi.send({ type: "control", control: "mute-assistant" });
        } catch {
          /* control may race call setup; transcripts still flow regardless */
        }
        this.h.onListening?.();
      });
      vapi.on("call-end", () => {
        this.running = false;
        this.h.onEnd?.();
      });
      vapi.on("error", (e) => {
        this.running = false;
        this.h.onError?.(e);
      });
      vapi.on("message", (m: { type?: string; role?: string; transcriptType?: string; transcript?: string }) => {
        if (m?.type !== "transcript" || typeof m.transcript !== "string") return;
        if (m.role && m.role !== "user") return; // only the human's speech
        if (m.transcriptType === "final") this.h.onFinal(m.transcript);
        else this.h.onPartial?.(m.transcript);
      });
      this.vapi = vapi;
    }

    try {
      await this.vapi.start(VITE_VAPI_ASSISTANT_ID);
      this.running = true;
      return true;
    } catch (e) {
      this.running = false;
      this.h.onError?.(e);
      return false;
    }
  }

  /** Stop the active call (idempotent). */
  stop(): void {
    this.running = false;
    this.vapi?.stop();
  }
}
