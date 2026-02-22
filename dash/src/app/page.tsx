"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { StatusData, TaskData } from "@/lib/api";
import { TaskCard } from "@/components/task-card";

export default function MissionControl() {
  const [status, setStatus] = useState<StatusData | null>(null);
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.status(), api.listTasks()])
      .then(([s, t]) => {
        setStatus(s);
        setTasks(t.tasks);
      })
      .catch((e) => setError(e.message));
  }, []);

  const handleRun = async (taskId: string) => {
    try {
      await api.runPipeline(taskId);
      const t = await api.listTasks();
      setTasks(t.tasks);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Pipeline failed");
    }
  };

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="flex items-center gap-4">
        <Image src="/logo.png" alt="OCCP Logo" width={48} height={48} className="rounded-lg" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="text-occp-primary">OCCP</span> Mission Control
          </h1>
          <p className="text-[var(--text-muted)] mt-1">
            Verified Autonomy Pipeline — Plan, Gate, Execute, Validate, Ship
          </p>
        </div>
      </div>

      {/* Status Bar */}
      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Platform", value: status.platform },
            { label: "Version", value: status.version },
            { label: "Tasks", value: String(status.tasks_count) },
            { label: "Audit Entries", value: String(status.audit_entries) },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="bg-occp-surface border border-occp-muted/30 rounded-xl p-4"
            >
              <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
                {label}
              </p>
              <p className="text-lg font-semibold mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="bg-occp-danger/10 border border-occp-danger/30 rounded-lg p-4 text-sm text-occp-danger">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-4 underline text-xs"
          >
            dismiss
          </button>
        </div>
      )}

      {/* VAP Stages Overview */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { step: "Plan", num: "1", desc: "Generate plan" },
          { step: "Gate", num: "2", desc: "Policy check" },
          { step: "Execute", num: "3", desc: "Run agent" },
          { step: "Validate", num: "4", desc: "Verify output" },
          { step: "Ship", num: "5", desc: "Deliver result" },
        ].map(({ step, num, desc }) => (
          <div
            key={step}
            className="bg-occp-surface border border-occp-muted/30 rounded-xl p-4 text-center"
          >
            <div className="w-10 h-10 rounded-full bg-occp-primary/15 text-occp-primary font-bold flex items-center justify-center mx-auto text-sm">
              {num}
            </div>
            <h3 className="font-semibold text-sm mt-2">{step}</h3>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">{desc}</p>
          </div>
        ))}
      </div>

      {/* Tasks */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Recent Tasks</h2>
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
          <div className="bg-occp-surface border border-occp-muted/30 rounded-xl p-12 text-center text-[var(--text-muted)]">
            <p className="text-lg font-medium">No tasks yet</p>
            <p className="text-sm mt-1">
              Create a task from the Pipeline page or via the API
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
