"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AgentData } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
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
          <h1 className="text-2xl font-bold tracking-tight">Agents</h1>
          <p className="text-[var(--text-muted)] text-sm mt-1">
            Register and manage autonomous agents in the pipeline
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-occp-primary hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {showForm ? "Cancel" : "Register Agent"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-occp-danger/10 border border-occp-danger/30 rounded-lg p-4 text-sm text-occp-danger flex justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="underline text-xs">
            dismiss
          </button>
        </div>
      )}

      {/* Registration Form */}
      {showForm && (
        <div className="bg-occp-surface border border-occp-muted/30 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold">Register New Agent</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              type="text"
              placeholder="Agent type (e.g. code-reviewer)"
              value={agentType}
              onChange={(e) => setAgentType(e.target.value)}
              className="bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50"
            />
            <input
              type="text"
              placeholder="Display name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50"
            />
            <input
              type="text"
              placeholder="Capabilities (comma-separated)"
              value={capabilities}
              onChange={(e) => setCapabilities(e.target.value)}
              className="bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50"
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs text-[var(--text-muted)] mb-1 block">
                  Max concurrent
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={maxConcurrent}
                  onChange={(e) => setMaxConcurrent(Number(e.target.value))}
                  className="w-full bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-[var(--text-muted)] mb-1 block">
                  Timeout (sec)
                </label>
                <input
                  type="number"
                  min={1}
                  max={3600}
                  value={timeoutSeconds}
                  onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                  className="w-full bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50"
                />
              </div>
            </div>
          </div>
          <button
            onClick={handleRegister}
            disabled={submitting || !agentType.trim() || !displayName.trim()}
            className="px-6 py-2 bg-occp-primary hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {submitting ? "Registering..." : "Register"}
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
        <div className="bg-occp-surface border border-occp-muted/30 rounded-xl p-12 text-center text-[var(--text-muted)]">
          <p className="text-lg font-medium">No agents registered</p>
          <p className="text-sm mt-1">
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
    <div className="bg-occp-surface border border-occp-muted/30 rounded-xl p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-base">{agent.display_name}</h3>
          <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
            {agent.agent_type}
          </p>
        </div>
        <div className="w-2.5 h-2.5 rounded-full bg-occp-success mt-1.5" title="Registered" />
      </div>

      {/* Capabilities */}
      {agent.capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {agent.capabilities.map((cap) => (
            <span
              key={cap}
              className="text-xs px-2 py-0.5 rounded-full bg-occp-primary/10 text-occp-primary"
            >
              {cap}
            </span>
          ))}
        </div>
      )}

      {/* Config */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-[var(--text-muted)]">Concurrency</span>
          <p className="font-medium">{agent.max_concurrent}</p>
        </div>
        <div>
          <span className="text-[var(--text-muted)]">Timeout</span>
          <p className="font-medium">{agent.timeout_seconds}s</p>
        </div>
      </div>

      {/* Actions */}
      <div className="pt-2 border-t border-occp-muted/20">
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-occp-danger">Confirm delete?</span>
            <button
              onClick={onDelete}
              className="text-xs px-3 py-1 bg-occp-danger/20 text-occp-danger rounded-md hover:bg-occp-danger/30 transition-colors"
            >
              Yes
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="text-xs px-3 py-1 bg-white/5 text-[var(--text-muted)] rounded-md hover:bg-white/10 transition-colors"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="text-xs text-[var(--text-muted)] hover:text-occp-danger transition-colors"
          >
            Unregister
          </button>
        )}
      </div>
    </div>
  );
}
