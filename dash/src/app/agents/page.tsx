"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AgentData } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [agentType, setAgentType] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [maxConcurrent, setMaxConcurrent] = useState(1);
  const [timeoutSeconds, setTimeoutSeconds] = useState(300);

  const loadAgents = async () => {
    try {
      const res = await api.listAgents();
      setAgents(res.agents);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load agents");
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  const handleRegister = async () => {
    if (!agentType.trim() || !displayName.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.registerAgent({
        agent_type: agentType.trim(),
        display_name: displayName.trim(),
        capabilities: capabilities
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean),
        max_concurrent: maxConcurrent,
        timeout_seconds: timeoutSeconds,
      });
      setAgentType("");
      setDisplayName("");
      setCapabilities("");
      setMaxConcurrent(1);
      setTimeoutSeconds(300);
      setShowForm(false);
      await loadAgents();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (type: string) => {
    setError(null);
    try {
      await api.deleteAgent(type);
      await loadAgents();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-pixel text-sm tracking-wide">
            <span className="text-occp-primary text-glow">AGENTS</span>
          </h1>
          <p className="text-[var(--text-muted)] text-xs font-mono mt-2">
            Register and manage autonomous agents in the pipeline
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className={showForm ? "retro-btn" : "retro-btn-primary"}
        >
          {showForm ? "CANCEL" : "REGISTER"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4 flex justify-between items-center">
          <div>
            <span className="font-pixel text-[9px] text-occp-danger mr-2">?ERROR</span>
            <span className="text-sm text-occp-danger font-mono">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] font-mono"
          >
            [DISMISS]
          </button>
        </div>
      )}

      {/* Registration Form */}
      {showForm && (
        <div className="retro-card p-6 space-y-4 crt-glow">
          <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
            Register New Agent
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              type="text"
              placeholder="Agent type (e.g. code-reviewer)"
              value={agentType}
              onChange={(e) => setAgentType(e.target.value)}
              className="retro-input"
            />
            <input
              type="text"
              placeholder="Display name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="retro-input"
            />
            <input
              type="text"
              placeholder="Capabilities (comma-separated)"
              value={capabilities}
              onChange={(e) => setCapabilities(e.target.value)}
              className="retro-input"
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block font-pixel text-[7px] text-[var(--text-muted)] mb-1.5 uppercase tracking-widest">
                  Max concurrent
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={maxConcurrent}
                  onChange={(e) => setMaxConcurrent(Number(e.target.value))}
                  className="retro-input w-full"
                />
              </div>
              <div className="flex-1">
                <label className="block font-pixel text-[7px] text-[var(--text-muted)] mb-1.5 uppercase tracking-widest">
                  Timeout (sec)
                </label>
                <input
                  type="number"
                  min={1}
                  max={3600}
                  value={timeoutSeconds}
                  onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                  className="retro-input w-full"
                />
              </div>
            </div>
          </div>
          <button
            onClick={handleRegister}
            disabled={submitting || !agentType.trim() || !displayName.trim()}
            className="retro-btn-primary"
          >
            {submitting ? "REGISTERING..." : "REGISTER"}
          </button>
        </div>
      )}

      {/* Agent Grid */}
      {agents.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard
              key={agent.agent_type}
              agent={agent}
              onDelete={() => handleDelete(agent.agent_type)}
            />
          ))}
        </div>
      ) : (
        <div className="retro-card p-12 text-center crt-glow">
          <p className="font-pixel text-[10px] text-[var(--text-muted)]">
            NO AGENTS REGISTERED
          </p>
          <p className="text-sm text-[var(--text-muted)] font-mono mt-3">
            Register an agent to start using the pipeline
          </p>
        </div>
      )}
    </div>
  );
}

function AgentCard({
  agent,
  onDelete,
}: {
  agent: AgentData;
  onDelete: () => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div className="retro-card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-mono font-bold text-sm">{agent.display_name}</h3>
          <p className="text-[10px] text-occp-accent font-mono mt-0.5">
            {agent.agent_type}
          </p>
        </div>
        <div className="w-2.5 h-2.5 rounded-full bg-occp-success mt-1.5 animate-pulse" title="Registered" />
      </div>

      {agent.capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {agent.capabilities.map((cap) => (
            <span
              key={cap}
              className="text-[10px] px-2 py-0.5 rounded font-mono bg-occp-primary/10 text-occp-primary border border-occp-primary/20"
            >
              {cap}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div>
          <span className="text-[var(--text-muted)] text-[10px]">CONCURRENCY</span>
          <p className="font-bold text-occp-accent">{agent.max_concurrent}</p>
        </div>
        <div>
          <span className="text-[var(--text-muted)] text-[10px]">TIMEOUT</span>
          <p className="font-bold text-occp-accent">{agent.timeout_seconds}s</p>
        </div>
      </div>

      <div className="pt-2 border-t border-occp-muted/20">
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-occp-danger font-mono">CONFIRM?</span>
            <button
              onClick={onDelete}
              className="text-xs px-3 py-1 bg-occp-danger/20 text-occp-danger rounded hover:bg-occp-danger/30 transition-colors font-mono"
            >
              YES
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="text-xs px-3 py-1 bg-white/5 text-[var(--text-muted)] rounded hover:bg-white/10 transition-colors font-mono"
            >
              NO
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="text-xs text-[var(--text-muted)] hover:text-occp-danger transition-colors font-mono"
          >
            UNREGISTER
          </button>
        )}
      </div>
    </div>
  );
}
