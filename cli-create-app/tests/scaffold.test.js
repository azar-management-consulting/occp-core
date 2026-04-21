import { describe, it, before, after } from "node:test";
import { strictEqual, ok } from "node:assert";
import { readFileSync, rmSync, mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI = join(__dirname, "..", "src", "index.js");

describe("create-occp-app CLI", () => {
  let tmpDir;
  before(() => {
    tmpDir = mkdtempSync(join(tmpdir(), "occp-cli-test-"));
  });
  after(() => {
    try {
      rmSync(tmpDir, { recursive: true, force: true });
    } catch {}
  });

  it("prints help with --help", () => {
    const r = spawnSync("node", [CLI, "--help"], {
      encoding: "utf8",
    });
    strictEqual(r.status, 0);
    ok(r.stdout.includes("create-occp-app"), "help mentions name");
    ok(r.stdout.includes("--template"), "help mentions --template");
    ok(r.stdout.includes("hello-agent"), "help lists hello-agent");
  });

  it("scaffolds hello-agent non-interactively", () => {
    const name = "scaffold-test-" + Date.now();
    const r = spawnSync(
      "node",
      [CLI, name, "--template", "hello-agent", "--yes"],
      { encoding: "utf8", cwd: tmpDir },
    );
    strictEqual(r.status, 0, `exit ${r.status}: ${r.stderr}`);
    const dest = join(tmpDir, name);
    ok(existsSync(dest), "project directory created");
    ok(existsSync(join(dest, "package.json")), "package.json copied");
    ok(existsSync(join(dest, "src/agent.js")), "src/agent.js copied");
    ok(existsSync(join(dest, "AGENTS.md")), "AGENTS.md copied");
    const pkg = JSON.parse(readFileSync(join(dest, "package.json"), "utf8"));
    strictEqual(pkg.name, name, "package.json name rewritten");
    strictEqual(pkg.version, "0.0.1", "version reset to 0.0.1");
  });

  it("refuses to overwrite existing directory", () => {
    const name = "collision-test-" + Date.now();
    const first = spawnSync(
      "node",
      [CLI, name, "--template", "hello-agent", "--yes"],
      { encoding: "utf8", cwd: tmpDir },
    );
    strictEqual(first.status, 0);
    const second = spawnSync(
      "node",
      [CLI, name, "--template", "hello-agent", "--yes"],
      { encoding: "utf8", cwd: tmpDir },
    );
    ok(second.status !== 0, "second run exits non-zero");
  });
});
