/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Development switch: render the committed reference run instead of calling
   *  the backend. Never a fallback — see `api.ts`. */
  readonly VITE_USE_FIXTURES?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
