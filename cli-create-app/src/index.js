#!/usr/bin/env node
/**
 * create-occp-app — scaffold a new OCCP agent project.
 *
 * Usage:
 *   npx create-occp-app@latest my-agent
 *   npx create-occp-app@latest my-agent --template hello-agent --yes
 *
 * Templates reference `templates/*` in the occp-core repo. In production
 * this CLI would fetch from a CDN / GitHub; in development we resolve to
 * sibling directories for fast iteration.
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync, statSync, existsSync, cpSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { argv, cwd, exit } from "node:process";

import * as p from "@clack/prompts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Resolve the templates root — sibling to cli-create-app/ in the monorepo.
const TEMPLATES_ROOT = resolve(__dirname, "..", "..", "templates");

const TEMPLATES = {
  "hello-agent": {
    name: "hello-agent",
    description: "20-line Node starter — your first verified agent",
    languages: ["TypeScript", "JavaScript"],
  },
  "rag-pipeline": {
    name: "rag-pipeline",
    description: "Retrieval + verified generation (stub — use hello-agent for now)",
    languages: ["Python", "TypeScript"],
    stub: true,
  },
  "mcp-server": {
    name: "mcp-server",
    description: "Custom Model Context Protocol server (stub — use hello-agent)",
    languages: ["TypeScript"],
    stub: true,
  },
  scheduler: {
    name: "scheduler",
    description: "Cron-scheduled agents (stub — use hello-agent)",
    languages: ["Node"],
    stub: true,
  },
};

function parseArgs() {
  const args = argv.slice(2);
  const out = { name: null, template: null, yes: false, help: false };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "-h" || a === "--help") out.help = true;
    else if (a === "-y" || a === "--yes") out.yes = true;
    else if (a === "--template") out.template = args[++i];
    else if (!out.name && !a.startsWith("-")) out.name = a;
  }
  return out;
}

function printHelp() {
  console.log(`
create-occp-app — scaffold a new OCCP agent project.

USAGE
  npx create-occp-app@latest [name] [options]

OPTIONS
  --template <name>   one of: ${Object.keys(TEMPLATES).join(", ")}
  --yes, -y           accept all defaults, no prompts
  --help, -h          this help

EXAMPLES
  npx create-occp-app@latest my-agent
  npx create-occp-app@latest my-agent --template hello-agent --yes
`);
}

async function main() {
  const args = parseArgs();
  if (args.help) {
    printHelp();
    return;
  }

  p.intro("🧠 create-occp-app — scaffold a new OCCP agent");

  // 1. Project name
  let name = args.name;
  if (!name) {
    const answer = await p.text({
      message: "Project name?",
      placeholder: "my-agent",
      validate: (v) => {
        if (!v) return "Name required";
        if (!/^[a-z0-9][a-z0-9-]*$/.test(v))
          return "Lowercase letters, numbers, hyphens only";
      },
    });
    if (p.isCancel(answer)) {
      p.cancel("Cancelled.");
      exit(0);
    }
    name = String(answer);
  }

  // 2. Template
  let templateKey = args.template;
  if (!templateKey && !args.yes) {
    const choice = await p.select({
      message: "Template?",
      options: Object.entries(TEMPLATES).map(([k, t]) => ({
        value: k,
        label: t.name,
        hint: t.description + (t.stub ? " [stub]" : ""),
      })),
    });
    if (p.isCancel(choice)) {
      p.cancel("Cancelled.");
      exit(0);
    }
    templateKey = String(choice);
  }
  templateKey ??= "hello-agent";
  if (!TEMPLATES[templateKey]) {
    p.cancel(`Unknown template: ${templateKey}`);
    exit(1);
  }
  if (TEMPLATES[templateKey].stub) {
    p.log.warn(
      `"${templateKey}" is a stub for v0.10.x. Falling back to hello-agent.`,
    );
    templateKey = "hello-agent";
  }

  // 3. Resolve source + destination
  const src = join(TEMPLATES_ROOT, templateKey);
  const dest = resolve(cwd(), name);

  if (!existsSync(src)) {
    p.cancel(
      `Template source missing: ${src}\n` +
        `(In production the CLI fetches from GitHub; dev needs sibling templates/ tree.)`,
    );
    exit(2);
  }
  if (existsSync(dest)) {
    p.cancel(`Destination already exists: ${dest}`);
    exit(3);
  }

  const spin = p.spinner();
  spin.start(`Copying ${templateKey} → ${relative(cwd(), dest) || dest}`);

  // 4. Recursive copy, skip node_modules + .git
  const skip = new Set(["node_modules", ".git", ".DS_Store"]);
  mkdirSync(dest, { recursive: true });
  const stack = [{ s: src, d: dest }];
  while (stack.length) {
    const { s, d } = stack.pop();
    for (const entry of readdirSync(s)) {
      if (skip.has(entry)) continue;
      const sPath = join(s, entry);
      const dPath = join(d, entry);
      const st = statSync(sPath);
      if (st.isDirectory()) {
        mkdirSync(dPath, { recursive: true });
        stack.push({ s: sPath, d: dPath });
      } else {
        cpSync(sPath, dPath);
      }
    }
  }

  // 5. Rewrite package.json name
  const pkgPath = join(dest, "package.json");
  if (existsSync(pkgPath)) {
    const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
    pkg.name = name;
    pkg.version = "0.0.1";
    writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n", "utf8");
  }

  spin.stop("Copied.");

  // 6. Next steps
  p.note(
    [
      `cd ${name}`,
      `cp .env.example .env`,
      `# edit .env — set OCCP_API_KEY from https://dash.occp.ai/onboarding`,
      `npm install`,
      `npm start`,
    ].join("\n"),
    "Next steps",
  );

  p.outro("Done. Happy shipping.");
}

main().catch((err) => {
  console.error("[create-occp-app]", err?.message ?? err);
  exit(10);
});
