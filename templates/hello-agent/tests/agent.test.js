import { describe, it } from "node:test";
import { strictEqual, ok } from "node:assert";
import { echoTool } from "../src/tools/echo.js";

describe("echoTool", () => {
  it("has canonical shape", () => {
    strictEqual(echoTool.name, "echo");
    strictEqual(typeof echoTool.description, "string");
    strictEqual(echoTool.parameters.type, "object");
    strictEqual(typeof echoTool.run, "function");
  });

  it("echoes input unchanged", async () => {
    const result = await echoTool.run({ message: "hello" });
    strictEqual(result.echoed, "hello");
    ok(result.ts, "timestamp present");
    ok(!Number.isNaN(Date.parse(result.ts)), "timestamp parses");
  });
});
