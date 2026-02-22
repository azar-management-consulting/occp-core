"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TaskData, PipelineResult } from "@/lib/api";
import { usePipelineWS } from "@/lib/ws";
import { TaskCard } from "@/components/task-card";
import { VAPProgress } from "@/components/vap-progress";

export default function PipelinePage() {
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const { events, connected } = usePipelineWS(activeTaskId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [riskLevel, setRiskLevel] = useState("low");

  useEffect(() => {
    api.listTasks().then((t) => setTasks(t.tasks)).catch(() => {});
  }, []);

  const refreshTasks = async () => {
    const t = await api.listTasks();
    setTasks(t.tasks);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const task = await api.createTask({
        name,
        description,
        agent_type: "general",
        risk_level: riskLevel,
      });
      setName("");
      setDescription("");
      await refreshTasks();
      setActiveTaskId(task.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (taskId: string) => {
    setError(null);
    setResult(null);
    setActiveTaskId(taskId);
    try {
      const r = await api.runPipeline(taskId);
      setResult(r);
      await refreshTasks();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Pipeline failed");
      await refreshTasks();
    }
  };

  const latestStatus =
    events.length > 0 ? events[events.length - 1].status || "unknown" : null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-pixel text-sm tracking-wide">
          <span className="text-occp-primary text-glow">PIPELINE</span>
        </h1>
        <p className="text-[var(--text-muted)] text-xs font-mono mt-2">
          Create tasks and run them through the Verified Autonomy Pipeline
        </p>
      </div>

      {/* Create Task Form */}
      <div className="retro-card p-6 space-y-4 crt-glow">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          New Task
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="text"
            placeholder="Task name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="retro-input"
          />
          <input
            type="text"
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="retro-input"
          />
          <div className="flex gap-2">
            <select
              value={riskLevel}
              onChange={(e) => setRiskLevel(e.target.value)}
              className="retro-select flex-1"
            >
              <option value="low">Low Risk</option>
              <option value="medium">Medium Risk</option>
              <option value="high">High Risk</option>
              <option value="critical">Critical Risk</option>
            </select>
            <button
              onClick={handleCreate}
              disabled={creating || !name.trim()}
              className="retro-btn-primary"
            >
              {creating ? "..." : "CREATE"}
            </button>
          </div>
        </div>
      </div>

      {/* Live Pipeline Monitor */}
      {activeTaskId && (
        <div className="retro-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
              Live Pipeline
            </h2>
            <div className="flex items-center gap-2 text-xs font-mono">
              <div
                className={`w-2 h-2 rounded-full ${connected ? "bg-occp-success animate-pulse" : "bg-occp-danger"}`}
              />
              <span className="text-[var(--text-muted)]">
                {connected ? "CONNECTED" : "DISCONNECTED"}
              </span>
            </div>
          </div>

          <VAPProgress status={latestStatus || "pending"} />

          {events.length > 0 && (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {events.map((evt, i) => (
                <div
                  key={i}
                  className="text-xs font-mono text-[var(--text-muted)] flex gap-4"
                >
                  <span className="text-occp-accent/50">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="text-[var(--text)]">{evt.event}</span>
                  {evt.status && (
                    <span className="text-occp-primary">&rarr; {evt.status}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {result && (
            <div
              className={`text-sm font-mono p-3 rounded-lg ${
                result.success
                  ? "bg-occp-success/10 text-occp-success border border-occp-success/30"
                  : "bg-occp-danger/10 text-occp-danger border border-occp-danger/30"
              }`}
            >
              {result.success ? "PIPELINE COMPLETE" : "PIPELINE FAILED"}
              {result.error && ` — ${result.error}`}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4">
          <span className="font-pixel text-[9px] text-occp-danger mr-2">?ERROR</span>
          <span className="text-sm text-occp-danger font-mono">{error}</span>
        </div>
      )}

      {/* Task List */}
      <div className="space-y-4">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          All Tasks
        </h2>
        {tasks.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks.map((t) => (
              <TaskCard
                key={t.id}
                id={t.id}
                name={t.name}
                description={t.description}
                status={t.status}
                risk_level={t.risk_level}
                created_at={t.created_at}
                onRun={() => handleRun(t.id)}
              />
            ))}
          </div>
        ) : (
          <p className="text-[var(--text-muted)] text-sm font-mono">
            No tasks yet. Create one above.
          </p>
        )}
      </div>
    </div>
  );
}
