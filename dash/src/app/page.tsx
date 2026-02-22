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
    <div className="space-y-10">
      {/* Hero — C64 Boot Sequence */}
      <div className="retro-card p-8 crt-glow">
        <div className="flex items-start gap-5">
          <div className="relative flex-shrink-0">
            <Image src="/logo.png" alt="OCCP Logo" width={56} height={56} className="rounded-lg" />
            <div className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-occp-success animate-pulse" />
          </div>
          <div className="space-y-2 min-w-0">
            <div className="font-pixel text-[9px] text-occp-primary/50 tracking-wider">
              **** OPENCLOUD CONTROL PLANE V0.5.0 ****
            </div>
            <h1 className="font-pixel text-base sm:text-lg leading-relaxed tracking-wide">
              <span className="text-occp-primary text-glow">OCCP</span>{" "}
              <span className="text-[var(--text)]">MISSION CONTROL</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] font-mono">
              Verified Autonomy Pipeline &mdash; Plan, Gate, Execute, Validate, Ship
            </p>
            <p className="text-xs text-occp-accent font-mono mt-1">
              READY.<span className="inline-block w-2 h-3.5 bg-occp-primary ml-1 animate-blink align-middle" />
            </p>
          </div>
        </div>
      </div>

      {/* System Status */}
      {status && (
        <div className="space-y-3">
          <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
            System Status
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "PLATFORM", value: status.platform, color: "text-occp-primary" },
              { label: "VERSION", value: status.version, color: "text-occp-accent" },
              { label: "TASKS", value: String(status.tasks_count), color: "text-occp-success" },
              { label: "AUDIT LOG", value: String(status.audit_entries), color: "text-occp-secondary" },
            ].map(({ label, value, color }) => (
              <div key={label} className="retro-card p-4">
                <p className="text-[10px] text-[var(--text-muted)] font-mono uppercase tracking-widest">
                  {label}
                </p>
                <p className={`text-lg font-bold font-mono mt-1.5 ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-pixel text-[9px] text-occp-danger">?ERROR</span>
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

      {/* VAP Pipeline */}
      <div className="space-y-3">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          Verified Autonomy Pipeline
        </h2>
        <div className="grid grid-cols-5 gap-3">
          {[
            { step: "PLAN", num: "01", desc: "Generate plan", color: "text-occp-primary" },
            { step: "GATE", num: "02", desc: "Policy check", color: "text-occp-secondary" },
            { step: "EXEC", num: "03", desc: "Run agent", color: "text-occp-accent" },
            { step: "VALID", num: "04", desc: "Verify output", color: "text-occp-success" },
            { step: "SHIP", num: "05", desc: "Deliver result", color: "text-occp-warning" },
          ].map(({ step, num, desc, color }) => (
            <div key={step} className="retro-card p-4 text-center group hover:border-occp-primary/40">
              <div className={`font-pixel text-lg ${color} mb-2`}>{num}</div>
              <h3 className="font-pixel text-[8px] tracking-wider">{step}</h3>
              <p className="text-[11px] text-[var(--text-muted)] font-mono mt-1.5">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Tasks */}
      <div className="space-y-4">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          Recent Tasks
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
          <div className="retro-card p-12 text-center crt-glow">
            <p className="font-pixel text-[10px] text-[var(--text-muted)]">NO TASKS LOADED</p>
            <p className="text-sm text-[var(--text-muted)] font-mono mt-3">
              Create a task from the Pipeline page or via the API
            </p>
            <p className="text-xs text-occp-accent font-mono mt-4">
              RUN &quot;/pipeline&quot;
              <span className="inline-block w-2 h-3 bg-occp-primary ml-1 animate-blink align-middle" />
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
