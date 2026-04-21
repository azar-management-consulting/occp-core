"use client";

import { useState } from "react";

type Lang = "python" | "ts" | "curl";

const SNIPPETS: Record<Lang, string> = {
  python: `# pip install occp
from occp import ControlPlane

cp = ControlPlane(policy="policies/finance.rego")

result = cp.run(
    agent="claude-opus-4-7",
    task="Refund order #4521 if return window is open",
)
# PLAN → VERIFY → APPROVE → EXECUTE → AUDIT
print(result.audit_chain_id)`,

  ts: `import { ControlPlane } from "@occp/sdk";

const cp = new ControlPlane({
  policy: "policies/finance.rego",
});

const { auditChainId } = await cp.run({
  agent: "claude-opus-4-7",
  task: "Refund order #4521",
});`,

  curl: `curl -X POST https://api.occp.ai/api/v1/pipelines \\
  -H "Authorization: Bearer $OCCP_KEY" \\
  -d '{
    "agent": "claude-opus-4-7",
    "task": "Refund order #4521",
    "policy": "finance"
  }'`,
};

const LABEL: Record<Lang, string> = {
  python: "Python",
  ts: "TypeScript",
  curl: "cURL",
};

export function CodeTabs() {
  const [active, setActive] = useState<Lang>("python");

  return (
    <div className="w-full overflow-hidden rounded-lg border border-border-subtle bg-bg-elev shadow-xl">
      <div className="flex items-center border-b border-border-subtle bg-bg px-4 py-2">
        {(Object.keys(SNIPPETS) as Lang[]).map((lang) => (
          <button
            key={lang}
            onClick={() => setActive(lang)}
            className={`mr-4 text-sm font-medium transition ${
              active === lang ? "text-brand" : "text-fg-muted hover:text-fg"
            }`}
            type="button"
            aria-selected={active === lang}
            role="tab"
          >
            {LABEL[lang]}
          </button>
        ))}
        <div className="ml-auto flex gap-1">
          <span className="h-3 w-3 rounded-full bg-red-500/70" />
          <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
          <span className="h-3 w-3 rounded-full bg-green-500/70" />
        </div>
      </div>
      <pre
        className="mono overflow-x-auto p-6 text-sm leading-relaxed text-fg"
        data-testid={`snippet-${active}`}
      >
        <code>{SNIPPETS[active]}</code>
      </pre>
    </div>
  );
}
