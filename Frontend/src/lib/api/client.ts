import createClient from "openapi-fetch";

import { API_ORIGIN, authFetch } from "@/lib/api/auth";
import type { paths } from "@/lib/api/schema";

/**
 * Typed API client (types generated from Backend/openapi.json by `npm run gen:api`).
 * Every request goes through authFetch: Bearer token, and on 401 one refresh + one retry.
 *
 *   const user = unwrap(await api.GET("/api/v1/users/me"));
 *
 * The generated paths already include /api/v1, so baseUrl is just the backend origin.
 */
export const api = createClient<paths>({
  baseUrl: API_ORIGIN,
  credentials: "include",
  fetch: (request) => authFetch(request),
});
