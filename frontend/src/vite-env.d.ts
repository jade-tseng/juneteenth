/// <reference types="vite/client" />

// Vapi creds, injected at build time (Phase 4, gated). Optional — absent in the
// default build, in which case typed text is the trigger.
interface ImportMetaEnv {
  readonly VITE_VAPI_PUBLIC_KEY?: string;
  readonly VITE_VAPI_ASSISTANT_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
