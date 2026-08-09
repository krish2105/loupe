/**
 * Base URL of the core API.
 *
 * Empty until the API is deployed. §5 keeps the web app talking to the core
 * API rather than the database, so this being unset simply disables the
 * features that need it instead of breaking the page.
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
