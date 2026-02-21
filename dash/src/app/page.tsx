export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-bold text-occp-dark mb-4">
          OCCP <span className="text-occp-primary">Mission Control</span>
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl">
          OpenCloud Control Plane — Verified Autonomy Pipeline for AI agents.
          Plan, gate, execute, validate, and ship with confidence.
        </p>
      </div>

      {/* Pipeline Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 w-full max-w-5xl mb-12">
        {[
          { step: "Plan", icon: "📋", color: "bg-blue-50 border-blue-200" },
          { step: "Gate", icon: "🛡️", color: "bg-purple-50 border-purple-200" },
          { step: "Execute", icon: "⚡", color: "bg-amber-50 border-amber-200" },
          { step: "Validate", icon: "✅", color: "bg-green-50 border-green-200" },
          { step: "Ship", icon: "🚀", color: "bg-cyan-50 border-cyan-200" },
        ].map(({ step, icon, color }) => (
          <div
            key={step}
            className={`${color} border rounded-xl p-6 text-center shadow-sm`}
          >
            <div className="text-3xl mb-2">{icon}</div>
            <h3 className="font-semibold text-slate-800">{step}</h3>
            <p className="text-sm text-slate-500 mt-1">Ready</p>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="flex gap-4">
        <button className="px-6 py-3 bg-occp-primary text-white rounded-lg font-medium hover:bg-blue-700 transition-colors">
          New Pipeline
        </button>
        <button className="px-6 py-3 border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50 transition-colors">
          View Agents
        </button>
        <button className="px-6 py-3 border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50 transition-colors">
          Audit Log
        </button>
      </div>

      {/* Footer */}
      <footer className="mt-16 text-sm text-slate-400">
        OCCP v0.1.0 — Azar Management Consulting
      </footer>
    </main>
  );
}
