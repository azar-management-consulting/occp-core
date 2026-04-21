#!/usr/bin/env node
/**
 * Build-time generator for llms.txt + llms-full.txt (llmstxt.org spec).
 *
 * Reads all MDX under content/docs/**\/*.mdx, extracts frontmatter
 * (title, description), and writes:
 *
 *   public/llms.txt       — structured index for LLM discovery
 *   public/llms-full.txt  — every MDX body concatenated (for RAG indexing)
 *
 * Zero dependencies — runs with Node 20+ built-ins.
 */
import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const DOCS_DIR = join(ROOT, "content", "docs");
const OUT_DIR = join(ROOT, "public");

const SITE_URL = process.env.OCCP_DOCS_SITE_URL ?? "https://docs.occp.ai";

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p));
    else if (p.endsWith(".mdx")) out.push(p);
  }
  return out;
}

function parseFrontmatter(body) {
  if (!body.startsWith("---")) return { meta: {}, rest: body };
  const end = body.indexOf("\n---", 3);
  if (end === -1) return { meta: {}, rest: body };
  const raw = body.slice(3, end).trim();
  const rest = body.slice(end + 4).replace(/^\n+/, "");
  const meta = {};
  for (const line of raw.split("\n")) {
    const m = line.match(/^([a-zA-Z_][\w-]*)\s*:\s*(.*)$/);
    if (m) meta[m[1]] = m[2].replace(/^['"]|['"]$/g, "").trim();
  }
  return { meta, rest };
}

function urlFor(relPath) {
  const noExt = relPath.replace(/\.mdx$/, "").replace(/\/index$/, "");
  return `${SITE_URL}/docs/${noExt}`;
}

const files = walk(DOCS_DIR).sort();
const index = [];
const full = [];

for (const file of files) {
  const body = readFileSync(file, "utf8");
  const { meta, rest } = parseFrontmatter(body);
  const rel = relative(DOCS_DIR, file).replaceAll("\\", "/");
  const url = urlFor(rel);
  index.push({
    title: meta.title ?? rel,
    description: meta.description ?? "",
    url: `${url}.md`,
    path: rel,
  });
  full.push(`# ${meta.title ?? rel}\n\n${rest}\n\n`);
}

// Sort index into top-level groups (index first, then alpha by path).
index.sort((a, b) => {
  if (a.path === "index.mdx") return -1;
  if (b.path === "index.mdx") return 1;
  return a.path.localeCompare(b.path);
});

const llmsTxt = [
  "# OCCP — OpenCloud Control Plane",
  "",
  "> Agent Control Plane with Verified Autonomy Pipeline.",
  "> Every autonomous action verified, logged, and reversible — before it runs.",
  "",
  "## Documentation",
  "",
  ...index.map((e) => `- [${e.title}](${e.url}): ${e.description}`),
  "",
  "## Optional",
  "",
  `- [API Reference (OpenAPI JSON)](https://api.occp.ai/api/v1/openapi.json)`,
  `- [GitHub Repository](https://github.com/azar-management-consulting/occp-core)`,
  "",
].join("\n");

mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(join(OUT_DIR, "llms.txt"), llmsTxt, "utf8");
writeFileSync(join(OUT_DIR, "llms-full.txt"), full.join(""), "utf8");

console.log(
  `[llms-txt] wrote ${index.length} entries → public/llms.txt (${llmsTxt.length} bytes)` +
    ` and public/llms-full.txt (${full.join("").length} bytes)`,
);
