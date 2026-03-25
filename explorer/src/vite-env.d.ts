/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** Optional; only for local dev — sent as X-API-Key when WIKIFS_API_KEY is set on the API */
  readonly VITE_WIKIFS_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
