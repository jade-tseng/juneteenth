// Vapi STT scaffold (CLAUDE.md §4.1, W1) — STUB ONLY, gated behind creds.
//
// No Vapi credentials are available in this build, so this is intentionally a
// no-op unless BOTH VITE_VAPI_PUBLIC_KEY and VITE_VAPI_ASSISTANT_ID are set at
// build time. When they are absent (the default), tryStartVapi() returns false
// immediately and typed text remains the trigger — nothing blocks on Vapi.
//
// When creds exist, wire the @vapi-ai/web SDK here: start a call, listen for
// final transcripts, and forward each to onTranscript (which the app routes to
// POST /api/sign). The SDK is not a dependency yet; add it when enabling Vapi.

export interface VapiHandlers {
  /** Called with each final STT transcript. */
  onTranscript: (text: string) => void;
  /** Optional: called when the mic opens, to flip the UI to "listening". */
  onListening?: () => void;
}

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

/**
 * Initialize Vapi if (and only if) creds are present. Returns true when the
 * integration was started, false when gated off (the default) — callers keep
 * the typed-text path in that case.
 */
export function tryStartVapi(_handlers: VapiHandlers): boolean {
  if (!vapiConfigured()) {
    // gated: no creds, no Vapi. Typed text drives the demo.
    return false;
  }
  // ── enable path (not exercised without creds) ──────────────────────────────
  // const { default: Vapi } = await import("@vapi-ai/web");
  // const vapi = new Vapi(VITE_VAPI_PUBLIC_KEY!);
  // vapi.on("call-start", () => _handlers.onListening?.());
  // vapi.on("message", (m) => {
  //   if (m.type === "transcript" && m.transcriptType === "final") {
  //     _handlers.onTranscript(m.transcript);
  //   }
  // });
  // vapi.start(VITE_VAPI_ASSISTANT_ID!);
  console.info("[vapi] creds present but SDK not bundled in this build");
  return false;
}
