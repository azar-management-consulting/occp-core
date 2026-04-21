#!/usr/bin/env node
/**
 * hello-agent — your first OCCP agent (20 LoC)
 *
 * Posts a task to the OCCP Brain API, waits for the Verified Autonomy
 * Pipeline to finish, and prints the result.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Minimal .env loader — no external deps.
function loadEnv(file = ".env") {
  try {
    const raw = readFileSync(resolve(process.cwd(), file), "utf8");
    for (const line of raw.split("\n")) {
      const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
      if (m && !process.env[m[1]]) {
        process.env[m[1]] = m[2].replace(/^['"]|['"]$/g, "");
      }
    }
  } catch {
    /* no .env — rely on environment */
  }
}
loadEnv();

const API_KEY = process.env.OCCP_API_KEY;
const API_URL = process.env.OCCP_API_URL ?? "https://api.occp.ai";

if (!API_KEY || API_KEY.startsWith("occp_live_sk_xxxxx")) {
  console.error(
    "[hello-agent] OCCP_API_KEY is missing. Edit .env and set your real key.\n" +
      "  Get one at https://dash.occp.ai/onboarding"
  );
  process.exit(1);
}

const task = "Say hello and confirm the pipeline is working.";

console.log(`[hello-agent] sending task to ${API_URL} ...`);

const response = await fetch(`${API_URL}/api/v1/brain/message`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${API_KEY}`,
  },
  body: JSON.stringify({ message: task }),
});

if (!response.ok) {
  const text = await response.text();
  console.error(`[hello-agent] HTTP ${response.status}: ${text.slice(0, 200)}`);
  process.exit(2);
}

const data = await response.json();
const output = data.response ?? data.output ?? data.message ?? JSON.stringify(data);
console.log(`[hello-agent] pipeline result: ${data.status ?? "ok"}`);
console.log(`[hello-agent] output: ${output}`);
