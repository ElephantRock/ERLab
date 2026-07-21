/// <reference types="vite/client" />

// Vite client types — provides ImportMetaEnv (import.meta.env) used by
// src/lib/sentry.ts, src/components/pipeline/stage-model-selector.tsx,
// and any other module reading VITE_* environment variables.
//
// Without this reference, tsc reports TS2339 'Property env does not exist
// on type ImportMeta'. This is the standard Vite mechanism, not a
// suppression: it loads the real ambient types shipped with vite.

interface ImportMetaEnv {
  readonly VITE_SENTRY_DSN?: string;
  readonly MODE: string;
  readonly DEV: boolean;
  readonly PROD: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
