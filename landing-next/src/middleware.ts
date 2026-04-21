import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

/**
 * next-intl middleware.
 *
 * - `/` is redirected to `/<locale>` based on Accept-Language, falling back
 *   to `en` (routing.defaultLocale).
 * - All other paths must match the locale pattern below.
 */
export default createMiddleware(routing);

export const config = {
  // Match:
  //   - bare `/`
  //   - any path starting with a supported locale
  // Exclude: _next, _vercel, api, static assets (files with an extension).
  matcher: ["/", "/(en|hu|de|fr|es|it|pt)/:path*"],
};
