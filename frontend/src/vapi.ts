// Vapi STT integration (CLAUDE.md §4.1, W1).
//
// The browser uses the Vapi *public* key + an assistant id (both VITE_ env vars,
// statically inlined by Vite at build time). The assistant is configured
// transcription-only ("ASL Signing — STT only"); we consume final user
// transcripts and forward them to POST /api/sign, then stop the call so the
// assistant never speaks back.
//
// When the env vars are absent (e.g. a build without creds), initVapi() returns
// null and the caller keeps the typed-text / mic-mock path — nothing breaks.

import Vapi from "@vapi-ai/web";

export interface VapiHandlers {
  /** Called with each final STT transcript (user speech). */
  onTranscript: (text: string) => void;
  /** Called when the mic call opens, to flip the UI to "listening". */
  onListening?: () => void;
  /** Called on a Vapi error so the UI can recover. */
  onError?: (err: unknown) => void;
}

export interface VapiController {
  /** Open the mic and start a transcription call. */
  start: () => Promise<void>;
  /** End the call (also auto-called after a final transcript). */
  stop: () => void;
}

interface VapiEnv {
  VITE_VAPI_PUBLIC_KEY?: string;
  VITE_VAPI_ASSISTANT_ID?: string;
}

function readEnv(): VapiEnv {
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

/**
 * Build a Vapi controller if (and only if) creds are present; otherwise null.
 * Registers transcript/listening/error listeners once.
 */
export function initVapi(handlers: VapiHandlers): VapiController | null {
  const { VITE_VAPI_PUBLIC_KEY, VITE_VAPI_ASSISTANT_ID } = readEnv();
  if (!VITE_VAPI_PUBLIC_KEY || !VITE_VAPI_ASSISTANT_ID) return null;

  const vapi = new Vapi(VITE_VAPI_PUBLIC_KEY);

  vapi.on("call-start", () => handlers.onListening?.());

  vapi.on("message", (msg: any) => {
    // We only care about the speaker's final transcript.
    if (
      msg?.type === "transcript" &&
      msg.transcriptType === "final" &&
      msg.role !== "assistant"
    ) {
      const text = String(msg.transcript ?? "").trim();
      if (text) {
        handlers.onTranscript(text);
        vapi.stop(); // got the utterance — don't let the assistant respond
      }
    }
  });

  vapi.on("error", (err: unknown) => handlers.onError?.(err));

  return {
    start: () =>
      Promise.resolve(vapi.start(VITE_VAPI_ASSISTANT_ID!)).then(() => undefined),
    stop: () => vapi.stop(),
  };
}
