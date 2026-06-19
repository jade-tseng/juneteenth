/// <reference types="vite/client" />

// Vapi creds, injected at build time (Phase 4, gated). Optional — absent in the
// default build, in which case typed text is the trigger.
interface ImportMetaEnv {
  // Base URL for the SMPL-X model assets (smplx_neutral.json/.bin). Defaults to
  // the bundled "./smplx" in dev; set to the public smplx-model GCS URL in prod.
  readonly VITE_SMPLX_BASE?: string;
  readonly VITE_VAPI_PUBLIC_KEY?: string;
  readonly VITE_VAPI_ASSISTANT_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
