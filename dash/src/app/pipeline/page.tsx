"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TaskData, PipelineResult, AgentData } from "@/lib/api";
import { usePipelineWS } from "@/lib/ws";
import { TaskCard } from "@/components/task-card";
import { VAPProgress } from "@/components/vap-progress";
import { useT } from "@/lib/i18n";

export default function PipelinePage() {
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const { events, connected } = usePipelineWS(activeTaskId);
  const t = useT();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agentType, setAgentType] = useState("general");
  const [riskLevel, setRiskLevel] = useState("low");

  useEffect(() => {
    api.listTasks().then((res) => setTasks(res.tasks)).catch(() => {});
    api.listAgents().then((a) => setAgents(a.agents)).catch(() => {});
  }, []);

  const refreshTasks = async () => {
    const res = await api.listTasks();
    setTasks(res.tasks);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const task = await api.createTask({
        name,
        description,
        agent_type: agentType,
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
          <span className="text-occp-primary text-glow">{t.pipeline.title}</span>
        </h1>
        <p className="section-desc mt-2">{t.pipeline.subtitle}</p>
      </div>

      {/* Create Task Form */}
      <div className="retro-card p-6 space-y-4 crt-glow">
        <h2 className="font-pixel text-[12px] text-occp-accent tracking-wider uppercase">
          {t.pipeline.newTask}
        </h2>
        <p className="section-desc">{t.pipeline.newTaskDesc}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <input
              type="text"
              placeholder={t.pipeline.taskName}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="retro-input w-full"
            />
          </div>
          <div>
            <input
              type="text"
              placeholder={t.pipeline.taskDescription}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="retro-input w-full"
            />
          </div>
          <select
            value={agentType}
            onChange={(e) => setAgentType(e.target.value)}
            className="retro-select"
          >
            {agents.length > 0 ? (
              agents.map((a) => (
                <option key={a.agent_type} value={a.agent_type}>
                  {a.display_name} ({a.agent_type})
                </option>
              ))
            ) : (
              <option value="general">General Assistant</option>
            )}
          </select>
          <div className="flex gap-2">
            <select
              value={riskLevel}
              onChange={(e) => setRiskLevel(e.target.value)}
              className="retro-select flex-1"
            >
              <option value="low">{t.pipeline.riskLow}</option>
              <option value="medium">{t.pipeline.riskMedium}</option>
              <option value="high">{t.pipeline.riskHigh}</option>
              <option value="critical">{t.pipeline.riskCritical}</option>
            </select>
            <button
              onClick={handleCreate}
              disabled={creating || !name.trim()}
              className="retro-btn-primary"
            >
              {creating ? t.pipeline.creating : t.pipeline.create}
            </button>
          </div>
        </div>
      </div>

      {/* Live Pipeline Monitor */}
      {activeTaskId && (
        <div className="retro-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-pixel text-[12px] text-occp-accent tracking-wider uppercase">
                {t.pipeline.livePipeline}
              </h2>
              <p className="section-desc">{t.pipeline.liveDesc}</p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono">
              <div
                className={`w-2 h-2 rounded-full ${connected ? "bg-occp-success animate-pulse" : "bg-occp-danger"}`}
              />
              <span className="text-[var(--text-muted)]">
                {connected ? t.pipeline.connected : t.pipeline.disconnected}
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
              {result.success ? t.pipeline.complete : t.pipeline.failed}
              {result.error && ` — ${result.error}`}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4">
          <span className="font-pixel text-[11px] text-occp-danger mr-2">?{t.common.error}</span>
          <span className="text-sm text-occp-danger font-mono">{error}</span>
        </div>
      )}

      {/* Task List */}
      <div className="space-y-4">
        <h2 className="font-pixel text-[12px] text-occp-accent tracking-wider uppercase">
          {t.pipeline.allTasks}
        </h2>
        <p className="section-desc">{t.pipeline.allTasksDesc}</p>
        {tasks.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks.map((task) => (
              <TaskCard
                key={task.id}
                id={task.id}
                name={task.name}
                description={task.description}
                status={task.status}
                risk_level={task.risk_level}
                created_at={task.created_at}
                onRun={() => handleRun(task.id)}
              />
            ))}
          </div>
        ) : (
          <p className="text-[var(--text-muted)] text-sm font-mono">
            {t.pipeline.noTasks} {t.pipeline.noTasksHint}
          </p>
        )}
      </div>
    </div>
  );
}
