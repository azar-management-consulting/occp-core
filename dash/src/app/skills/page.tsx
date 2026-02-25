"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SkillData } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillData[]>([]);
  const [totalImpact, setTotalImpact] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const t = useT();

  const loadSkills = async () => {
    try {
      const res = await api.listSkills();
      setSkills(res.skills);
      setTotalImpact(res.total_enabled_token_impact);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load skills");
    }
  };

  useEffect(() => {
    loadSkills();
  }, []);

  const handleToggle = async (skillId: string, currentEnabled: boolean) => {
    setToggling(skillId);
    setError(null);
    try {
      if (currentEnabled) {
        await api.disableSkill(skillId);
      } else {
        await api.enableSkill(skillId);
      }
      await loadSkills();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    } finally {
      setToggling(null);
    }
  };

  const enabledCount = skills.filter((s) => s.enabled).length;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-pixel text-sm tracking-wide">
            <span className="text-occp-primary text-glow">{t.skills.title}</span>
          </h1>
          <p className="section-desc mt-2">{t.skills.subtitle}</p>
        </div>
        <div className="text-right">
          <p className="font-pixel text-[11px] text-[var(--text-muted)] uppercase tracking-widest">
            {t.skills.totalImpact}
          </p>
          <p className="font-mono text-lg text-occp-accent font-bold">
            ~{Math.ceil(totalImpact / 4)} tokens
          </p>
          <p className="text-[11px] text-[var(--text-muted)] font-mono">
            {enabledCount}/{skills.length} {t.skills.enabled.toLowerCase()}
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4 flex justify-between items-center">
          <div>
            <span className="font-pixel text-[11px] text-occp-danger mr-2">✗ {t.common.error}</span>
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

      {/* Skills Grid */}
      {skills.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skills.map((skill) => (
            <div key={skill.id} className="retro-card p-5 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-mono font-bold text-sm">{skill.name}</h3>
                  <span className="text-[11px] px-2 py-0.5 rounded font-mono bg-occp-accent/10 text-occp-accent border border-occp-accent/20 mt-1 inline-block">
                    {skill.category}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] font-pixel px-1.5 py-0.5 rounded ${
                      skill.trusted
                        ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                        : "bg-occp-warning/10 text-occp-warning border border-occp-warning/20"
                    }`}
                  >
                    {skill.trusted ? t.skills.trusted : t.skills.untrusted}
                  </span>
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${
                      skill.enabled ? "bg-occp-success animate-pulse" : "bg-occp-muted/40"
                    }`}
                  />
                </div>
              </div>

              <p className="text-xs text-[var(--text-muted)] font-mono leading-relaxed">
                {skill.description}
              </p>

              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <span className="text-[var(--text-muted)] text-[11px]">{t.skills.tokenImpact}</span>
                  <p className="font-bold text-occp-accent">
                    ~{skill.token_impact_tokens} tokens
                  </p>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] text-[11px]">STATUS</span>
                  <p className={`font-bold ${skill.enabled ? "text-occp-success" : "text-[var(--text-muted)]"}`}>
                    {skill.enabled ? t.skills.enabled : t.skills.disabled}
                  </p>
                </div>
              </div>

              <button
                onClick={() => handleToggle(skill.id, skill.enabled)}
                disabled={toggling === skill.id}
                className={`w-full text-center text-xs font-mono py-2 rounded transition-all ${
                  skill.enabled
                    ? "bg-occp-danger/10 text-occp-danger border border-occp-danger/20 hover:bg-occp-danger/20"
                    : "retro-btn-primary"
                }`}
              >
                {toggling === skill.id
                  ? "..."
                  : skill.enabled
                    ? t.skills.disable
                    : t.skills.enable}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="retro-card p-12 text-center crt-glow">
          <p className="font-pixel text-[12px] text-[var(--text-muted)]">
            {t.skills.noSkills}
          </p>
        </div>
      )}
    </div>
  );
}
