import { ApiReference } from "@scalar/nextjs-api-reference";

export const GET = ApiReference({
  spec: { url: "https://api.occp.ai/openapi.json" },
  theme: "default",
  layout: "modern",
  hideDownloadButton: false,
  metaData: {
    title: "OCCP API Reference",
    description:
      "OCCP REST API v1 — 50+ endpoints for the Verified Autonomy Pipeline.",
  },
});
