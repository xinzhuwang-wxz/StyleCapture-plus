/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" builds the Style Party as a standalone site with no product API. */
  readonly VITE_PARTY_ONLY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
