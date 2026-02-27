"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { StatusData, TaskData } from "@/lib/api";
import { TaskCard } from "@/components/task-card";
import { LLMHealthPanel } from "@/components/llm-health-panel";
import { WelcomePanel } from "@/components/welcome-panel";
import { useT } from "@/lib/i18n";

export default function MissionControl() {
  const [status, setStatus] = useState<StatusData | null>(null);
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const t = useT();

  useEffect(() => {
    Promise.all([api.status(), api.listTasks()])
      .then(([s, tData]) => {
        setStatus(s);
        setTasks(tData.tasks);
      })
      .catch((e) => setError(e.message));
  }, []);

  const handleRun = async (taskId: string) => {
    try {
      await api.runPipeline(taskId);
      const tData = await api.listTasks();
      setTasks(tData.tasks);
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
            <div className="font-pixel text-[11px] text-occp-primary/50 tracking-wider">
              {t.home.bootLine}
            </div>
            <h1 className="font-pixel text-base sm:text-lg leading-relaxed tracking-wide">
              <span className="text-occp-primary text-glow">{t.home.title}</span>{" "}
              <span className="text-[var(--text)]">MISSION CONTROL</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] font-mono">
              {t.home.subtitle}
            </p>
            <p className="text-xs text-occp-accent font-mono mt-1">
              {t.home.ready}<span className="inline-block w-2 h-3.5 bg-occp-primary ml-1 animate-blink align-middle" />
            </p>
          </div>
        </div>
      </div>

      {/* System Status */}
      {status && (
        <div className="space-y-3">
          <div>
            <h2 className="font-pixel text-[13px] text-occp-accent tracking-wider uppercase">
              {t.home.systemStatus}
            </h2>
            <p className="section-desc">{t.home.systemStatusDesc}</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: t.home.platform, value: status.platform, color: "text-occp-primary" },
              { label: t.home.version, value: status.version, color: "text-occp-accent" },
              { label: t.home.tasks, value: String(status.tasks_count), color: "text-occp-success" },
              { label: t.home.auditLog, value: String(status.audit_entries), color: "text-occp-secondary" },
            ].map(({ label, value, color }) => (
              <div key={label} className="retro-card p-5">
                <p className="text-[12px] text-[var(--text-muted)] font-mono uppercase tracking-widest">
                  {label}
                </p>
                <p className={`text-xl font-bold font-mono mt-1.5 ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-pixel text-[11px] text-occp-danger">{t.common.error}</span>
            <span className="text-sm text-occp-danger font-mono">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] font-mono"
          >
            [{t.common.dismiss}]
          </button>
        </div>
      )}

      {/* Onboarding Welcome Panel */}
      <WelcomePanel />

      {/* LLM Providers Health */}
      <LLMHealthPanel />

      {/* Verified Autonomy Pipeline */}
      <div className="space-y-3">
        <div>
          <h2 className="font-pixel text-[13px] text-occp-accent tracking-wider uppercase">
            {t.home.vapTitle}
          </h2>
          <p className="section-desc">{t.home.vapDesc}</p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {[
            { step: t.home.plan, num: "01", desc: t.home.planDesc, color: "text-occp-primary" },
            { step: t.home.gate, num: "02", desc: t.home.gateDesc, color: "text-occp-secondary" },
            { step: t.home.exec, num: "03", desc: t.home.execDesc, color: "text-occp-accent" },
            { step: t.home.valid, num: "04", desc: t.home.validDesc, color: "text-occp-success" },
            { step: t.home.ship, num: "05", desc: t.home.shipDesc, color: "text-occp-warning" },
          ].map(({ step, num, desc, color }) => (
            <div key={step} className="retro-card p-5 text-center group hover:border-occp-primary/40">
              <div className={`font-pixel text-xl ${color} mb-2`}>{num}</div>
              <h3 className="font-pixel text-[12px] tracking-wider">{step}</h3>
              <p className="text-[12px] text-[var(--text-muted)] font-mono mt-1.5 break-words">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Tasks */}
      <div className="space-y-4">
        <div>
          <h2 className="font-pixel text-[13px] text-occp-accent tracking-wider uppercase">
            {t.home.recentTasks}
          </h2>
          <p className="section-desc">{t.home.recentTasksDesc}</p>
        </div>
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
          <div className="retro-card p-12 text-center crt-glow">
            <p className="font-pixel text-[12px] text-[var(--text-muted)]">{t.home.noTasks}</p>
            <p className="text-base text-[var(--text-muted)] font-mono mt-3">
              {t.home.noTasksHint}
            </p>
            <p className="text-sm text-occp-accent font-mono mt-4">
              {t.home.noTasksCmd}
              <span className="inline-block w-2 h-3 bg-occp-primary ml-1 animate-blink align-middle" />
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
