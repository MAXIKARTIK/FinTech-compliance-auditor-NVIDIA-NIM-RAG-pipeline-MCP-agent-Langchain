/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend API base URL. Defaults to "/api" (served behind the Nginx/Vite proxy). */
  readonly VITE_API_BASE?: string;
  /** API key sent as the X-API-Key header on write requests. */
  readonly VITE_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
