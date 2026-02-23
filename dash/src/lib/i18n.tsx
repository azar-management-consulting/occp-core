"use client";

import { createContext, useCallback, useContext, useMemo, useState, useEffect } from "react";
import type { ReactNode } from "react";

export type Locale = "en" | "es" | "de" | "fr" | "zh" | "hu";

export const LOCALES: { code: Locale; label: string; native: string }[] = [
  { code: "en", label: "English", native: "English" },
  { code: "es", label: "Spanish", native: "Espa\u00f1ol" },
  { code: "de", label: "German", native: "Deutsch" },
  { code: "fr", label: "French", native: "Fran\u00e7ais" },
  { code: "zh", label: "Chinese", native: "\u4e2d\u6587" },
  { code: "hu", label: "Hungarian", native: "Magyar" },
];

const STORAGE_KEY = "occp_lang";

/* ── Translation shape ─────────────────────────────────── */

export interface T {
  nav: {
    control: string;
    pipeline: string;
    agents: string;
    policy: string;
    audit: string;
    controlDesc: string;
    pipelineDesc: string;
    agentsDesc: string;
    policyDesc: string;
    auditDesc: string;
    logout: string;
  };
  home: {
    bootLine: string;
    title: string;
    subtitle: string;
    ready: string;
    systemStatus: string;
    systemStatusDesc: string;
    platform: string;
    version: string;
    tasks: string;
    auditLog: string;
    vapTitle: string;
    vapDesc: string;
    plan: string;
    gate: string;
    exec: string;
    valid: string;
    ship: string;
    planDesc: string;
    gateDesc: string;
    execDesc: string;
    validDesc: string;
    shipDesc: string;
    recentTasks: string;
    recentTasksDesc: string;
    noTasks: string;
    noTasksHint: string;
    noTasksCmd: string;
    llmTitle: string;
    llmDesc: string;
    allGo: string;
    degraded: string;
    online: string;
    calls: string;
    latency: string;
    errors: string;
    loading: string;
    unavailable: string;
  };
  pipeline: {
    title: string;
    subtitle: string;
    newTask: string;
    newTaskDesc: string;
    taskName: string;
    taskDescription: string;
    agentType: string;
    riskLevel: string;
    riskLow: string;
    riskMedium: string;
    riskHigh: string;
    riskCritical: string;
    create: string;
    creating: string;
    livePipeline: string;
    liveDesc: string;
    connected: string;
    disconnected: string;
    complete: string;
    failed: string;
    allTasks: string;
    allTasksDesc: string;
    noTasks: string;
    noTasksHint: string;
    noTasksCmd?: string;
  };
  agents: {
    title: string;
    subtitle: string;
    register: string;
    cancel: string;
    registerNew: string;
    registerNewDesc: string;
    typePlaceholder: string;
    typeHint: string;
    namePlaceholder: string;
    nameHint: string;
    capsPlaceholder: string;
    capsHint: string;
    maxConcurrent: string;
    maxConcurrentHint: string;
    timeout: string;
    timeoutHint: string;
    noAgents: string;
    noAgentsHint: string;
    concurrency: string;
    unregister: string;
    confirm: string;
    registering: string;
  };
  policy: {
    title: string;
    subtitle: string;
    safePrompt: string;
    injection: string;
    piiContent: string;
    presetsDesc: string;
    placeholder: string;
    evaluate: string;
    evaluating: string;
    approved: string;
    rejected: string;
    guardsPassed: string;
    inputDesc: string;
  };
  audit: {
    title: string;
    subtitle: string;
    entries: string;
    refresh: string;
    hashChain: string;
    valid: string;
    broken: string;
    time: string;
    actor: string;
    action: string;
    task: string;
    hash: string;
    noEntries: string;
    loading: string;
    chainDesc: string;
  };
  common: {
    error: string;
    dismiss: string;
    runPipeline: string;
    id: string;
  };
}

/* ── Translations ──────────────────────────────────────── */

const translations: Record<Locale, T> = {
  en: {
    nav: {
      control: "CONTROL",
      pipeline: "PIPELINE",
      agents: "AGENTS",
      policy: "POLICY",
      audit: "AUDIT",
      controlDesc: "Mission overview & system health",
      pipelineDesc: "Create tasks & run VAP pipeline",
      agentsDesc: "Agent registry & configuration",
      policyDesc: "Policy guard evaluation tool",
      auditDesc: "Immutable hash-chain audit log",
      logout: "LOGOUT",
    },
    home: {
      bootLine: "**** OPENCLOUD CONTROL PLANE V0.6.0 ****",
      title: "MISSION CONTROL",
      subtitle: "Verified Autonomy Pipeline \u2014 Plan, Gate, Execute, Validate, Ship",
      ready: "READY.",
      systemStatus: "System Status",
      systemStatusDesc: "Real-time platform health metrics and operational counters",
      platform: "PLATFORM",
      version: "VERSION",
      tasks: "TASKS",
      auditLog: "AUDIT LOG",
      vapTitle: "Verified Autonomy Pipeline",
      vapDesc: "Every task flows through five safety stages before delivery. Each stage must pass to proceed.",
      plan: "PLAN",
      gate: "GATE",
      exec: "EXEC",
      valid: "VALID",
      ship: "SHIP",
      planDesc: "AI generates an execution plan with risk assessment",
      gateDesc: "Policy guards check for injection, PII & resource limits",
      execDesc: "Agent executes the approved plan in a sandboxed environment",
      validDesc: "Output is verified against quality & safety constraints",
      shipDesc: "Validated result is delivered with full audit trail",
      recentTasks: "Recent Tasks",
      recentTasksDesc: "Latest tasks submitted to the pipeline. Click RUN to execute pending tasks.",
      noTasks: "NO TASKS LOADED",
      noTasksHint: "Create a task from the Pipeline page or via the API",
      noTasksCmd: 'RUN "/pipeline"',
      llmTitle: "LLM Providers",
      llmDesc: "Cascading failover chain status. Auto-refreshes every 30 seconds.",
      allGo: "\u25cf ALL SYSTEMS GO",
      degraded: "\u25b2 DEGRADED",
      online: "ONLINE",
      calls: "Calls",
      latency: "Latency",
      errors: "Errors",
      loading: "LOADING PROVIDER STATUS...",
      unavailable: "PROVIDER STATUS UNAVAILABLE",
    },
    pipeline: {
      title: "PIPELINE",
      subtitle: "Create tasks and run them through the Verified Autonomy Pipeline",
      newTask: "New Task",
      newTaskDesc: "Define a task with a name, description, agent type, and risk level. The task will be queued for pipeline execution.",
      taskName: "Task name",
      taskDescription: "Description (what should the agent accomplish?)",
      agentType: "Agent type",
      riskLevel: "Risk level",
      riskLow: "Low Risk",
      riskMedium: "Medium Risk",
      riskHigh: "High Risk",
      riskCritical: "Critical Risk",
      create: "CREATE",
      creating: "CREATING...",
      livePipeline: "Live Pipeline",
      liveDesc: "Real-time stage progression for the active task. Events stream via WebSocket.",
      connected: "CONNECTED",
      disconnected: "DISCONNECTED",
      complete: "PIPELINE COMPLETE",
      failed: "PIPELINE FAILED",
      allTasks: "All Tasks",
      allTasksDesc: "Complete history of tasks. Pending tasks can be executed by clicking RUN PIPELINE.",
      noTasks: "No tasks yet.",
      noTasksHint: "Create one above to get started.",
      noTasksCmd: 'RUN "/pipeline"',
    },
    agents: {
      title: "AGENTS",
      subtitle: "Register and manage autonomous agents in the pipeline",
      register: "REGISTER",
      cancel: "CANCEL",
      registerNew: "Register New Agent",
      registerNewDesc: "Define an agent with a unique type identifier, display name, and capabilities. Each agent type gets its own adapter routing.",
      typePlaceholder: "Agent type (e.g. code-reviewer)",
      typeHint: "Unique slug used in API calls and routing",
      namePlaceholder: "Display name",
      nameHint: "Human-readable label shown in the dashboard",
      capsPlaceholder: "Capabilities (comma-separated)",
      capsHint: "e.g. code-analysis, pr-review, security-scan",
      maxConcurrent: "Max concurrent",
      maxConcurrentHint: "Parallel execution limit",
      timeout: "Timeout (sec)",
      timeoutHint: "Max execution time per task",
      noAgents: "NO AGENTS REGISTERED",
      noAgentsHint: "Register an agent to start using the pipeline",
      concurrency: "CONCURRENCY",
      unregister: "UNREGISTER",
      confirm: "CONFIRM?",
      registering: "REGISTERING...",
    },
    policy: {
      title: "POLICY TESTER",
      subtitle: "Test content against OCCP policy guards \u2014 PII detection, prompt injection, and resource limits",
      safePrompt: "SAFE PROMPT",
      injection: "INJECTION",
      piiContent: "PII CONTENT",
      presetsDesc: "Quick-load test scenarios to evaluate different guard behaviors",
      placeholder: "Enter content to evaluate against policy guards...",
      evaluate: "EVALUATE",
      evaluating: "EVALUATING...",
      approved: "APPROVED",
      rejected: "REJECTED",
      guardsPassed: "guards passed",
      inputDesc: "Paste or type any content below. The policy engine will check it against all active guards and return pass/fail results.",
    },
    audit: {
      title: "AUDIT LOG",
      subtitle: "Tamper-evident SHA-256 hash chain of all pipeline operations",
      entries: "entries",
      refresh: "REFRESH",
      hashChain: "HASH CHAIN",
      valid: "VALID",
      broken: "BROKEN",
      time: "TIME",
      actor: "ACTOR",
      action: "ACTION",
      task: "TASK",
      hash: "HASH",
      noEntries: "NO AUDIT ENTRIES",
      loading: "LOADING AUDIT LOG...",
      chainDesc: "Each entry is cryptographically linked to the previous one. A broken chain indicates tampering.",
    },
    common: {
      error: "ERROR",
      dismiss: "DISMISS",
      runPipeline: "RUN PIPELINE",
      id: "ID",
    },
  },

  es: {
    nav: {
      control: "CONTROL",
      pipeline: "PIPELINE",
      agents: "AGENTES",
      policy: "POL\u00cdTICA",
      audit: "AUDITOR\u00cdA",
      controlDesc: "Visi\u00f3n general y salud del sistema",
      pipelineDesc: "Crear tareas y ejecutar pipeline VAP",
      agentsDesc: "Registro y configuraci\u00f3n de agentes",
      policyDesc: "Herramienta de evaluaci\u00f3n de pol\u00edticas",
      auditDesc: "Registro de auditor\u00eda inmutable",
      logout: "SALIR",
    },
    home: {
      bootLine: "**** OPENCLOUD CONTROL PLANE V0.6.0 ****",
      title: "CENTRO DE CONTROL",
      subtitle: "Pipeline de Autonom\u00eda Verificada \u2014 Planificar, Filtrar, Ejecutar, Validar, Entregar",
      ready: "LISTO.",
      systemStatus: "Estado del Sistema",
      systemStatusDesc: "M\u00e9tricas de salud de la plataforma en tiempo real",
      platform: "PLATAFORMA",
      version: "VERSI\u00d3N",
      tasks: "TAREAS",
      auditLog: "AUDITOR\u00cdA",
      vapTitle: "Pipeline de Autonom\u00eda Verificada",
      vapDesc: "Cada tarea pasa por cinco etapas de seguridad antes de la entrega.",
      plan: "PLAN",
      gate: "FILTRO",
      exec: "EJEC",
      valid: "VALID",
      ship: "ENVIAR",
      planDesc: "La IA genera un plan de ejecuci\u00f3n con evaluaci\u00f3n de riesgo",
      gateDesc: "Los guardias verifican inyecci\u00f3n, PII y l\u00edmites",
      execDesc: "El agente ejecuta el plan aprobado en entorno seguro",
      validDesc: "Se verifica la salida contra restricciones de calidad",
      shipDesc: "El resultado validado se entrega con registro completo",
      recentTasks: "Tareas Recientes",
      recentTasksDesc: "\u00daltimas tareas enviadas al pipeline.",
      noTasks: "SIN TAREAS",
      noTasksHint: "Cree una tarea desde Pipeline o la API",
      noTasksCmd: 'RUN "/pipeline"',
      llmTitle: "Proveedores LLM",
      llmDesc: "Estado de la cadena de conmutaci\u00f3n por error. Se actualiza cada 30s.",
      allGo: "\u25cf TODOS OPERATIVOS",
      degraded: "\u25b2 DEGRADADO",
      online: "EN L\u00cdNEA",
      calls: "Llamadas",
      latency: "Latencia",
      errors: "Errores",
      loading: "CARGANDO ESTADO...",
      unavailable: "ESTADO NO DISPONIBLE",
    },
    pipeline: {
      title: "PIPELINE",
      subtitle: "Cree tareas y ej\u00e9cutelas a trav\u00e9s del Pipeline de Autonom\u00eda Verificada",
      newTask: "Nueva Tarea",
      newTaskDesc: "Defina una tarea con nombre, descripci\u00f3n, tipo de agente y nivel de riesgo.",
      taskName: "Nombre de tarea",
      taskDescription: "Descripci\u00f3n (\u00bfqu\u00e9 debe lograr el agente?)",
      agentType: "Tipo de agente",
      riskLevel: "Nivel de riesgo",
      riskLow: "Riesgo Bajo",
      riskMedium: "Riesgo Medio",
      riskHigh: "Riesgo Alto",
      riskCritical: "Riesgo Cr\u00edtico",
      create: "CREAR",
      creating: "CREANDO...",
      livePipeline: "Pipeline en Vivo",
      liveDesc: "Progresi\u00f3n en tiempo real de la tarea activa v\u00eda WebSocket.",
      connected: "CONECTADO",
      disconnected: "DESCONECTADO",
      complete: "PIPELINE COMPLETADO",
      failed: "PIPELINE FALLIDO",
      allTasks: "Todas las Tareas",
      allTasksDesc: "Historial completo de tareas.",
      noTasks: "Sin tareas a\u00fan.",
      noTasksHint: "Cree una arriba para comenzar.",
      noTasksCmd: 'RUN "/pipeline"',
    },
    agents: {
      title: "AGENTES",
      subtitle: "Registre y gestione agentes aut\u00f3nomos en el pipeline",
      register: "REGISTRAR",
      cancel: "CANCELAR",
      registerNew: "Registrar Nuevo Agente",
      registerNewDesc: "Defina un agente con identificador \u00fanico, nombre y capacidades.",
      typePlaceholder: "Tipo de agente (ej. code-reviewer)",
      typeHint: "Slug \u00fanico para API y enrutamiento",
      namePlaceholder: "Nombre para mostrar",
      nameHint: "Etiqueta visible en el dashboard",
      capsPlaceholder: "Capacidades (separadas por coma)",
      capsHint: "ej. code-analysis, pr-review, security-scan",
      maxConcurrent: "M\u00e1x. concurrente",
      maxConcurrentHint: "L\u00edmite de ejecuci\u00f3n paralela",
      timeout: "Timeout (seg)",
      timeoutHint: "Tiempo m\u00e1ximo por tarea",
      noAgents: "SIN AGENTES REGISTRADOS",
      noAgentsHint: "Registre un agente para usar el pipeline",
      concurrency: "CONCURRENCIA",
      unregister: "ELIMINAR",
      confirm: "\u00bfCONFIRMAR?",
      registering: "REGISTRANDO...",
    },
    policy: {
      title: "PROBADOR DE POL\u00cdTICAS",
      subtitle: "Pruebe contenido contra los guardias OCCP \u2014 detecci\u00f3n PII, inyecci\u00f3n de prompts y l\u00edmites",
      safePrompt: "PROMPT SEGURO",
      injection: "INYECCI\u00d3N",
      piiContent: "CONTENIDO PII",
      presetsDesc: "Cargue escenarios de prueba r\u00e1pidos",
      placeholder: "Ingrese contenido para evaluar...",
      evaluate: "EVALUAR",
      evaluating: "EVALUANDO...",
      approved: "APROBADO",
      rejected: "RECHAZADO",
      guardsPassed: "guardias aprobados",
      inputDesc: "Pegue o escriba contenido. El motor evaluar\u00e1 contra todos los guardias activos.",
    },
    audit: {
      title: "AUDITOR\u00cdA",
      subtitle: "Cadena SHA-256 a prueba de manipulaciones de todas las operaciones",
      entries: "entradas",
      refresh: "ACTUALIZAR",
      hashChain: "CADENA HASH",
      valid: "V\u00c1LIDA",
      broken: "ROTA",
      time: "HORA",
      actor: "ACTOR",
      action: "ACCI\u00d3N",
      task: "TAREA",
      hash: "HASH",
      noEntries: "SIN ENTRADAS",
      loading: "CARGANDO...",
      chainDesc: "Cada entrada est\u00e1 vinculada criptogr\u00e1ficamente a la anterior.",
    },
    common: {
      error: "ERROR",
      dismiss: "CERRAR",
      runPipeline: "EJECUTAR PIPELINE",
      id: "ID",
    },
  },

  de: {
    nav: {
      control: "KONTROLLE",
      pipeline: "PIPELINE",
      agents: "AGENTEN",
      policy: "RICHTLINIE",
      audit: "AUDIT",
      controlDesc: "\u00dcbersicht & Systemzustand",
      pipelineDesc: "Aufgaben erstellen & VAP-Pipeline ausf\u00fchren",
      agentsDesc: "Agentenregistrierung & Konfiguration",
      policyDesc: "Richtlinien-Evaluierungstool",
      auditDesc: "Unver\u00e4nderliches Hash-Chain Audit-Log",
      logout: "ABMELDEN",
    },
    home: {
      bootLine: "**** OPENCLOUD CONTROL PLANE V0.6.0 ****",
      title: "KONTROLLZENTRUM",
      subtitle: "Verifizierte Autonomie-Pipeline \u2014 Planen, Pr\u00fcfen, Ausf\u00fchren, Validieren, Ausliefern",
      ready: "BEREIT.",
      systemStatus: "Systemstatus",
      systemStatusDesc: "Echtzeit-Gesundheitsmetriken der Plattform",
      platform: "PLATTFORM",
      version: "VERSION",
      tasks: "AUFGABEN",
      auditLog: "AUDIT-LOG",
      vapTitle: "Verifizierte Autonomie-Pipeline",
      vapDesc: "Jede Aufgabe durchl\u00e4uft f\u00fcnf Sicherheitsstufen vor der Auslieferung.",
      plan: "PLAN",
      gate: "GATE",
      exec: "AUSF.",
      valid: "VALID",
      ship: "AUSL.",
      planDesc: "KI erstellt einen Ausf\u00fchrungsplan mit Risikobewertung",
      gateDesc: "Richtlinien pr\u00fcfen auf Injection, PII & Limits",
      execDesc: "Agent f\u00fchrt den genehmigten Plan in Sandbox aus",
      validDesc: "Ausgabe wird gegen Qualit\u00e4ts- & Sicherheitsvorgaben gepr\u00fcft",
      shipDesc: "Validiertes Ergebnis wird mit vollst\u00e4ndigem Audit-Trail geliefert",
      recentTasks: "Letzte Aufgaben",
      recentTasksDesc: "Zuletzt eingereichte Pipeline-Aufgaben.",
      noTasks: "KEINE AUFGABEN GELADEN",
      noTasksHint: "Erstellen Sie eine Aufgabe\u00fcber Pipeline oder die API",
      noTasksCmd: 'RUN "/pipeline"',
      llmTitle: "LLM-Anbieter",
      llmDesc: "Kaskadierender Failover-Kettenstatus. Aktualisiert alle 30s.",
      allGo: "\u25cf ALLE SYSTEME OK",
      degraded: "\u25b2 BEEINTR\u00c4CHTIGT",
      online: "ONLINE",
      calls: "Aufrufe",
      latency: "Latenz",
      errors: "Fehler",
      loading: "LADE ANBIETERSTATUS...",
      unavailable: "STATUS NICHT VERF\u00dcGBAR",
    },
    pipeline: {
      title: "PIPELINE",
      subtitle: "Aufgaben erstellen und durch die Verifizierte Autonomie-Pipeline ausf\u00fchren",
      newTask: "Neue Aufgabe",
      newTaskDesc: "Definieren Sie eine Aufgabe mit Name, Beschreibung, Agententyp und Risikostufe.",
      taskName: "Aufgabenname",
      taskDescription: "Beschreibung (was soll der Agent erreichen?)",
      agentType: "Agententyp",
      riskLevel: "Risikostufe",
      riskLow: "Niedriges Risiko",
      riskMedium: "Mittleres Risiko",
      riskHigh: "Hohes Risiko",
      riskCritical: "Kritisches Risiko",
      create: "ERSTELLEN",
      creating: "ERSTELLE...",
      livePipeline: "Live-Pipeline",
      liveDesc: "Echtzeit-Fortschritt der aktiven Aufgabe via WebSocket.",
      connected: "VERBUNDEN",
      disconnected: "GETRENNT",
      complete: "PIPELINE ABGESCHLOSSEN",
      failed: "PIPELINE FEHLGESCHLAGEN",
      allTasks: "Alle Aufgaben",
      allTasksDesc: "Vollst\u00e4ndiger Aufgabenverlauf.",
      noTasks: "Noch keine Aufgaben.",
      noTasksHint: "Erstellen Sie oben eine Aufgabe.",
      noTasksCmd: 'RUN "/pipeline"',
    },
    agents: {
      title: "AGENTEN",
      subtitle: "Autonome Agenten in der Pipeline registrieren und verwalten",
      register: "REGISTRIEREN",
      cancel: "ABBRECHEN",
      registerNew: "Neuen Agenten Registrieren",
      registerNewDesc: "Definieren Sie einen Agenten mit eindeutigem Typ, Anzeigename und F\u00e4higkeiten.",
      typePlaceholder: "Agententyp (z.B. code-reviewer)",
      typeHint: "Eindeutiger Slug f\u00fcr API und Routing",
      namePlaceholder: "Anzeigename",
      nameHint: "Im Dashboard angezeigte Bezeichnung",
      capsPlaceholder: "F\u00e4higkeiten (kommagetrennt)",
      capsHint: "z.B. code-analysis, pr-review, security-scan",
      maxConcurrent: "Max. parallel",
      maxConcurrentHint: "Parallele Ausf\u00fchrungsgrenze",
      timeout: "Timeout (Sek.)",
      timeoutHint: "Max. Ausf\u00fchrungszeit pro Aufgabe",
      noAgents: "KEINE AGENTEN REGISTRIERT",
      noAgentsHint: "Registrieren Sie einen Agenten um die Pipeline zu nutzen",
      concurrency: "PARALLELIT\u00c4T",
      unregister: "ENTFERNEN",
      confirm: "BEST\u00c4TIGEN?",
      registering: "REGISTRIERE...",
    },
    policy: {
      title: "RICHTLINIEN-TESTER",
      subtitle: "Inhalte gegen OCCP-Richtlinien pr\u00fcfen \u2014 PII, Prompt-Injection & Limits",
      safePrompt: "SICHERER PROMPT",
      injection: "INJECTION",
      piiContent: "PII-INHALT",
      presetsDesc: "Schnelllade-Testszenarien f\u00fcr verschiedene Guard-Verhalten",
      placeholder: "Inhalt zur Richtlinienpr\u00fcfung eingeben...",
      evaluate: "PR\u00dcFEN",
      evaluating: "PR\u00dcFE...",
      approved: "GENEHMIGT",
      rejected: "ABGELEHNT",
      guardsPassed: "Guards bestanden",
      inputDesc: "Inhalt eingeben oder einf\u00fcgen. Der Motor pr\u00fcft gegen alle aktiven Guards.",
    },
    audit: {
      title: "AUDIT-LOG",
      subtitle: "Manipulationssichere SHA-256-Hash-Kette aller Pipeline-Operationen",
      entries: "Eintr\u00e4ge",
      refresh: "AKTUALISIEREN",
      hashChain: "HASH-KETTE",
      valid: "G\u00dcLTIG",
      broken: "GEBROCHEN",
      time: "ZEIT",
      actor: "AKTEUR",
      action: "AKTION",
      task: "AUFGABE",
      hash: "HASH",
      noEntries: "KEINE EINTR\u00c4GE",
      loading: "LADE AUDIT-LOG...",
      chainDesc: "Jeder Eintrag ist kryptographisch mit dem vorherigen verkn\u00fcpft.",
    },
    common: {
      error: "FEHLER",
      dismiss: "SCHLIESSEN",
      runPipeline: "PIPELINE STARTEN",
      id: "ID",
    },
  },

  fr: {
    nav: {
      control: "CONTR\u00d4LE",
      pipeline: "PIPELINE",
      agents: "AGENTS",
      policy: "POLITIQUE",
      audit: "AUDIT",
      controlDesc: "Aper\u00e7u de la mission & sant\u00e9 du syst\u00e8me",
      pipelineDesc: "Cr\u00e9er des t\u00e2ches & ex\u00e9cuter le pipeline VAP",
      agentsDesc: "Registre & configuration des agents",
      policyDesc: "Outil d'\u00e9valuation des politiques",
      auditDesc: "Journal d'audit cha\u00eene de hachage immuable",
      logout: "D\u00c9CONNEXION",
    },
    home: {
      bootLine: "**** OPENCLOUD CONTROL PLANE V0.6.0 ****",
      title: "CENTRE DE CONTR\u00d4LE",
      subtitle: "Pipeline d'Autonomie V\u00e9rifi\u00e9e \u2014 Planifier, Filtrer, Ex\u00e9cuter, Valider, Livrer",
      ready: "PR\u00caT.",
      systemStatus: "\u00c9tat du Syst\u00e8me",
      systemStatusDesc: "M\u00e9triques de sant\u00e9 de la plateforme en temps r\u00e9el",
      platform: "PLATEFORME",
      version: "VERSION",
      tasks: "T\u00c2CHES",
      auditLog: "JOURNAL D'AUDIT",
      vapTitle: "Pipeline d'Autonomie V\u00e9rifi\u00e9e",
      vapDesc: "Chaque t\u00e2che passe par cinq \u00e9tapes de s\u00e9curit\u00e9 avant la livraison.",
      plan: "PLAN",
      gate: "FILTRE",
      exec: "EX\u00c9C",
      valid: "VALID",
      ship: "LIVR.",
      planDesc: "L'IA g\u00e9n\u00e8re un plan d'ex\u00e9cution avec \u00e9valuation des risques",
      gateDesc: "Les gardes v\u00e9rifient l'injection, les PII & les limites",
      execDesc: "L'agent ex\u00e9cute le plan approuv\u00e9 en bac \u00e0 sable",
      validDesc: "La sortie est v\u00e9rifi\u00e9e contre les contraintes de qualit\u00e9",
      shipDesc: "Le r\u00e9sultat valid\u00e9 est livr\u00e9 avec piste d'audit compl\u00e8te",
      recentTasks: "T\u00e2ches R\u00e9centes",
      recentTasksDesc: "Derni\u00e8res t\u00e2ches soumises au pipeline.",
      noTasks: "AUCUNE T\u00c2CHE CHARG\u00c9E",
      noTasksHint: "Cr\u00e9ez une t\u00e2che depuis Pipeline ou l'API",
      noTasksCmd: 'RUN "/pipeline"',
      llmTitle: "Fournisseurs LLM",
      llmDesc: "\u00c9tat de la cha\u00eene de basculement en cascade. Actualisation auto 30s.",
      allGo: "\u25cf TOUS SYST\u00c8MES OK",
      degraded: "\u25b2 D\u00c9GRAD\u00c9",
      online: "EN LIGNE",
      calls: "Appels",
      latency: "Latence",
      errors: "Erreurs",
      loading: "CHARGEMENT DU STATUT...",
      unavailable: "STATUT INDISPONIBLE",
    },
    pipeline: {
      title: "PIPELINE",
      subtitle: "Cr\u00e9ez des t\u00e2ches et ex\u00e9cutez-les via le Pipeline d'Autonomie V\u00e9rifi\u00e9e",
      newTask: "Nouvelle T\u00e2che",
      newTaskDesc: "D\u00e9finissez une t\u00e2che avec nom, description, type d'agent et niveau de risque.",
      taskName: "Nom de la t\u00e2che",
      taskDescription: "Description (que doit accomplir l'agent ?)",
      agentType: "Type d'agent",
      riskLevel: "Niveau de risque",
      riskLow: "Risque Faible",
      riskMedium: "Risque Moyen",
      riskHigh: "Risque \u00c9lev\u00e9",
      riskCritical: "Risque Critique",
      create: "CR\u00c9ER",
      creating: "CR\u00c9ATION...",
      livePipeline: "Pipeline en Direct",
      liveDesc: "Progression en temps r\u00e9el de la t\u00e2che active via WebSocket.",
      connected: "CONNECT\u00c9",
      disconnected: "D\u00c9CONNECT\u00c9",
      complete: "PIPELINE TERMIN\u00c9",
      failed: "PIPELINE \u00c9CHOU\u00c9",
      allTasks: "Toutes les T\u00e2ches",
      allTasksDesc: "Historique complet des t\u00e2ches.",
      noTasks: "Pas encore de t\u00e2ches.",
      noTasksHint: "Cr\u00e9ez-en une ci-dessus.",
      noTasksCmd: 'RUN "/pipeline"',
    },
    agents: {
      title: "AGENTS",
      subtitle: "Enregistrer et g\u00e9rer les agents autonomes dans le pipeline",
      register: "ENREGISTRER",
      cancel: "ANNULER",
      registerNew: "Enregistrer un Nouvel Agent",
      registerNewDesc: "D\u00e9finissez un agent avec un type unique, un nom d'affichage et des capacit\u00e9s.",
      typePlaceholder: "Type d'agent (ex. code-reviewer)",
      typeHint: "Slug unique pour les appels API et le routage",
      namePlaceholder: "Nom d'affichage",
      nameHint: "Libell\u00e9 visible dans le tableau de bord",
      capsPlaceholder: "Capacit\u00e9s (s\u00e9par\u00e9es par virgule)",
      capsHint: "ex. code-analysis, pr-review, security-scan",
      maxConcurrent: "Max. parall\u00e8le",
      maxConcurrentHint: "Limite d'ex\u00e9cution parall\u00e8le",
      timeout: "D\u00e9lai (sec)",
      timeoutHint: "Dur\u00e9e max par t\u00e2che",
      noAgents: "AUCUN AGENT ENREGISTR\u00c9",
      noAgentsHint: "Enregistrez un agent pour utiliser le pipeline",
      concurrency: "PARALL\u00c9LISME",
      unregister: "SUPPRIMER",
      confirm: "CONFIRMER ?",
      registering: "ENREGISTREMENT...",
    },
    policy: {
      title: "TESTEUR DE POLITIQUE",
      subtitle: "Tester le contenu contre les gardes OCCP \u2014 PII, injection de prompts & limites",
      safePrompt: "PROMPT S\u00dbR",
      injection: "INJECTION",
      piiContent: "CONTENU PII",
      presetsDesc: "Sc\u00e9narios de test rapides pour diff\u00e9rents comportements de garde",
      placeholder: "Saisir du contenu \u00e0 \u00e9valuer...",
      evaluate: "\u00c9VALUER",
      evaluating: "\u00c9VALUATION...",
      approved: "APPROUV\u00c9",
      rejected: "REJET\u00c9",
      guardsPassed: "gardes pass\u00e9s",
      inputDesc: "Collez ou saisissez du contenu. Le moteur v\u00e9rifiera contre tous les gardes actifs.",
    },
    audit: {
      title: "JOURNAL D'AUDIT",
      subtitle: "Cha\u00eene de hachage SHA-256 inviolable de toutes les op\u00e9rations du pipeline",
      entries: "entr\u00e9es",
      refresh: "ACTUALISER",
      hashChain: "CHA\u00ceNE DE HACHAGE",
      valid: "VALIDE",
      broken: "CASS\u00c9E",
      time: "HEURE",
      actor: "ACTEUR",
      action: "ACTION",
      task: "T\u00c2CHE",
      hash: "HASH",
      noEntries: "AUCUNE ENTR\u00c9E",
      loading: "CHARGEMENT...",
      chainDesc: "Chaque entr\u00e9e est cryptographiquement li\u00e9e \u00e0 la pr\u00e9c\u00e9dente.",
    },
    common: {
      error: "ERREUR",
      dismiss: "FERMER",
      runPipeline: "EX\u00c9CUTER PIPELINE",
      id: "ID",
    },
  },

  zh: {
    nav: {
      control: "\u63a7\u5236",
      pipeline: "\u6d41\u6c34\u7ebf",
      agents: "\u4ee3\u7406",
      policy: "\u7b56\u7565",
      audit: "\u5ba1\u8ba1",
      controlDesc: "\u4efb\u52a1\u6982\u89c8\u4e0e\u7cfb\u7edf\u5065\u5eb7",
      pipelineDesc: "\u521b\u5efa\u4efb\u52a1\u5e76\u8fd0\u884cVAP\u6d41\u6c34\u7ebf",
      agentsDesc: "\u4ee3\u7406\u6ce8\u518c\u4e0e\u914d\u7f6e",
      policyDesc: "\u7b56\u7565\u5b88\u536b\u8bc4\u4f30\u5de5\u5177",
      auditDesc: "\u4e0d\u53ef\u7be1\u6539\u54c8\u5e0c\u94fe\u5ba1\u8ba1\u65e5\u5fd7",
      logout: "\u767b\u51fa",
    },
    home: {
      bootLine: "**** OPENCLOUD CONTROL PLANE V0.6.0 ****",
      title: "\u4efb\u52a1\u63a7\u5236\u4e2d\u5fc3",
      subtitle: "\u9a8c\u8bc1\u81ea\u4e3b\u6d41\u6c34\u7ebf \u2014 \u89c4\u5212\u3001\u95e8\u63a7\u3001\u6267\u884c\u3001\u9a8c\u8bc1\u3001\u4ea4\u4ed8",
      ready: "\u5c31\u7eea\u3002",
      systemStatus: "\u7cfb\u7edf\u72b6\u6001",
      systemStatusDesc: "\u5b9e\u65f6\u5e73\u53f0\u5065\u5eb7\u6307\u6807\u548c\u8fd0\u884c\u8ba1\u6570\u5668",
      platform: "\u5e73\u53f0",
      version: "\u7248\u672c",
      tasks: "\u4efb\u52a1",
      auditLog: "\u5ba1\u8ba1\u65e5\u5fd7",
      vapTitle: "\u9a8c\u8bc1\u81ea\u4e3b\u6d41\u6c34\u7ebf",
      vapDesc: "\u6bcf\u4e2a\u4efb\u52a1\u5728\u4ea4\u4ed8\u524d\u90fd\u4f1a\u901a\u8fc7\u4e94\u4e2a\u5b89\u5168\u9636\u6bb5\u3002",
      plan: "\u89c4\u5212",
      gate: "\u95e8\u63a7",
      exec: "\u6267\u884c",
      valid: "\u9a8c\u8bc1",
      ship: "\u4ea4\u4ed8",
      planDesc: "AI\u751f\u6210\u5305\u542b\u98ce\u9669\u8bc4\u4f30\u7684\u6267\u884c\u8ba1\u5212",
      gateDesc: "\u7b56\u7565\u5b88\u536b\u68c0\u67e5\u6ce8\u5165\u3001PII\u548c\u8d44\u6e90\u9650\u5236",
      execDesc: "\u4ee3\u7406\u5728\u6c99\u7bb1\u73af\u5883\u4e2d\u6267\u884c\u5df2\u6279\u51c6\u7684\u8ba1\u5212",
      validDesc: "\u8f93\u51fa\u6309\u8d28\u91cf\u548c\u5b89\u5168\u7ea6\u675f\u8fdb\u884c\u9a8c\u8bc1",
      shipDesc: "\u9a8c\u8bc1\u7ed3\u679c\u968f\u5b8c\u6574\u5ba1\u8ba1\u8ff9\u4ea4\u4ed8",
      recentTasks: "\u6700\u8fd1\u4efb\u52a1",
      recentTasksDesc: "\u6700\u65b0\u63d0\u4ea4\u5230\u6d41\u6c34\u7ebf\u7684\u4efb\u52a1\u3002",
      noTasks: "\u65e0\u4efb\u52a1",
      noTasksHint: "\u4ece\u6d41\u6c34\u7ebf\u9875\u9762\u6216API\u521b\u5efa\u4efb\u52a1",
      noTasksCmd: 'RUN "/pipeline"',
      llmTitle: "LLM\u63d0\u4f9b\u5546",
      llmDesc: "\u7ea7\u8054\u6545\u969c\u8f6c\u79fb\u94fe\u72b6\u6001\u300230\u79d2\u81ea\u52a8\u5237\u65b0\u3002",
      allGo: "\u25cf \u6240\u6709\u7cfb\u7edf\u6b63\u5e38",
      degraded: "\u25b2 \u5df2\u964d\u7ea7",
      online: "\u5728\u7ebf",
      calls: "\u8c03\u7528",
      latency: "\u5ef6\u8fdf",
      errors: "\u9519\u8bef",
      loading: "\u52a0\u8f7d\u63d0\u4f9b\u5546\u72b6\u6001...",
      unavailable: "\u63d0\u4f9b\u5546\u72b6\u6001\u4e0d\u53ef\u7528",
    },
    pipeline: {
      title: "\u6d41\u6c34\u7ebf",
      subtitle: "\u521b\u5efa\u4efb\u52a1\u5e76\u901a\u8fc7\u9a8c\u8bc1\u81ea\u4e3b\u6d41\u6c34\u7ebf\u8fd0\u884c",
      newTask: "\u65b0\u4efb\u52a1",
      newTaskDesc: "\u5b9a\u4e49\u4efb\u52a1\u540d\u79f0\u3001\u63cf\u8ff0\u3001\u4ee3\u7406\u7c7b\u578b\u548c\u98ce\u9669\u7b49\u7ea7\u3002",
      taskName: "\u4efb\u52a1\u540d\u79f0",
      taskDescription: "\u63cf\u8ff0\uff08\u4ee3\u7406\u5e94\u5b8c\u6210\u4ec0\u4e48\uff1f\uff09",
      agentType: "\u4ee3\u7406\u7c7b\u578b",
      riskLevel: "\u98ce\u9669\u7b49\u7ea7",
      riskLow: "\u4f4e\u98ce\u9669",
      riskMedium: "\u4e2d\u98ce\u9669",
      riskHigh: "\u9ad8\u98ce\u9669",
      riskCritical: "\u4e25\u91cd\u98ce\u9669",
      create: "\u521b\u5efa",
      creating: "\u521b\u5efa\u4e2d...",
      livePipeline: "\u5b9e\u65f6\u6d41\u6c34\u7ebf",
      liveDesc: "\u901a\u8fc7WebSocket\u5b9e\u65f6\u8ddf\u8e2a\u6d3b\u52a8\u4efb\u52a1\u8fdb\u5ea6\u3002",
      connected: "\u5df2\u8fde\u63a5",
      disconnected: "\u5df2\u65ad\u5f00",
      complete: "\u6d41\u6c34\u7ebf\u5b8c\u6210",
      failed: "\u6d41\u6c34\u7ebf\u5931\u8d25",
      allTasks: "\u6240\u6709\u4efb\u52a1",
      allTasksDesc: "\u5b8c\u6574\u7684\u4efb\u52a1\u5386\u53f2\u8bb0\u5f55\u3002",
      noTasks: "\u6682\u65e0\u4efb\u52a1\u3002",
      noTasksHint: "\u5728\u4e0a\u65b9\u521b\u5efa\u4e00\u4e2a\u4ee5\u5f00\u59cb\u3002",
      noTasksCmd: 'RUN "/pipeline"',
    },
    agents: {
      title: "\u4ee3\u7406",
      subtitle: "\u5728\u6d41\u6c34\u7ebf\u4e2d\u6ce8\u518c\u548c\u7ba1\u7406\u81ea\u4e3b\u4ee3\u7406",
      register: "\u6ce8\u518c",
      cancel: "\u53d6\u6d88",
      registerNew: "\u6ce8\u518c\u65b0\u4ee3\u7406",
      registerNewDesc: "\u5b9a\u4e49\u4e00\u4e2a\u5177\u6709\u552f\u4e00\u7c7b\u578b\u6807\u8bc6\u3001\u663e\u793a\u540d\u79f0\u548c\u80fd\u529b\u7684\u4ee3\u7406\u3002",
      typePlaceholder: "\u4ee3\u7406\u7c7b\u578b\uff08\u4f8b\u5982 code-reviewer\uff09",
      typeHint: "\u7528\u4e8eAPI\u8c03\u7528\u548c\u8def\u7531\u7684\u552f\u4e00\u6807\u8bc6",
      namePlaceholder: "\u663e\u793a\u540d\u79f0",
      nameHint: "\u5728\u4eea\u8868\u677f\u4e2d\u663e\u793a\u7684\u6807\u7b7e",
      capsPlaceholder: "\u80fd\u529b\uff08\u9017\u53f7\u5206\u9694\uff09",
      capsHint: "\u4f8b\u5982 code-analysis, pr-review, security-scan",
      maxConcurrent: "\u6700\u5927\u5e76\u53d1",
      maxConcurrentHint: "\u5e76\u884c\u6267\u884c\u9650\u5236",
      timeout: "\u8d85\u65f6\uff08\u79d2\uff09",
      timeoutHint: "\u6bcf\u4e2a\u4efb\u52a1\u7684\u6700\u5927\u6267\u884c\u65f6\u95f4",
      noAgents: "\u65e0\u6ce8\u518c\u4ee3\u7406",
      noAgentsHint: "\u6ce8\u518c\u4e00\u4e2a\u4ee3\u7406\u4ee5\u5f00\u59cb\u4f7f\u7528\u6d41\u6c34\u7ebf",
      concurrency: "\u5e76\u53d1\u6570",
      unregister: "\u53d6\u6d88\u6ce8\u518c",
      confirm: "\u786e\u8ba4\uff1f",
      registering: "\u6ce8\u518c\u4e2d...",
    },
    policy: {
      title: "\u7b56\u7565\u6d4b\u8bd5\u5668",
      subtitle: "\u6d4b\u8bd5\u5185\u5bb9\u662f\u5426\u7b26\u5408OCCP\u7b56\u7565\u5b88\u536b \u2014 PII\u3001\u63d0\u793a\u6ce8\u5165\u548c\u8d44\u6e90\u9650\u5236",
      safePrompt: "\u5b89\u5168\u63d0\u793a",
      injection: "\u6ce8\u5165",
      piiContent: "PII\u5185\u5bb9",
      presetsDesc: "\u5feb\u901f\u52a0\u8f7d\u6d4b\u8bd5\u573a\u666f",
      placeholder: "\u8f93\u5165\u8981\u8bc4\u4f30\u7684\u5185\u5bb9...",
      evaluate: "\u8bc4\u4f30",
      evaluating: "\u8bc4\u4f30\u4e2d...",
      approved: "\u5df2\u6279\u51c6",
      rejected: "\u5df2\u62d2\u7edd",
      guardsPassed: "\u5b88\u536b\u901a\u8fc7",
      inputDesc: "\u7c98\u8d34\u6216\u8f93\u5165\u5185\u5bb9\u3002\u5f15\u64ce\u5c06\u5bf9\u6240\u6709\u6d3b\u52a8\u5b88\u536b\u8fdb\u884c\u68c0\u67e5\u3002",
    },
    audit: {
      title: "\u5ba1\u8ba1\u65e5\u5fd7",
      subtitle: "\u6240\u6709\u6d41\u6c34\u7ebf\u64cd\u4f5c\u7684\u9632\u7be1\u6539SHA-256\u54c8\u5e0c\u94fe",
      entries: "\u6761\u76ee",
      refresh: "\u5237\u65b0",
      hashChain: "\u54c8\u5e0c\u94fe",
      valid: "\u6709\u6548",
      broken: "\u5df2\u635f\u574f",
      time: "\u65f6\u95f4",
      actor: "\u64cd\u4f5c\u8005",
      action: "\u64cd\u4f5c",
      task: "\u4efb\u52a1",
      hash: "\u54c8\u5e0c",
      noEntries: "\u65e0\u5ba1\u8ba1\u6761\u76ee",
      loading: "\u52a0\u8f7d\u5ba1\u8ba1\u65e5\u5fd7...",
      chainDesc: "\u6bcf\u4e2a\u6761\u76ee\u4e0e\u524d\u4e00\u4e2a\u52a0\u5bc6\u94fe\u63a5\u3002",
    },
    common: {
      error: "\u9519\u8bef",
      dismiss: "\u5173\u95ed",
      runPipeline: "\u8fd0\u884c\u6d41\u6c34\u7ebf",
      id: "ID",
    },
  },

  hu: {
    nav: {
      control: "VEZ\u00c9RL\u0150",
      pipeline: "PIPELINE",
      agents: "\u00c1GENSEK",
      policy: "SZAB\u00c1LY",
      audit: "AUDIT",
      controlDesc: "Misszi\u00f3 \u00e1ttekint\u00e9s \u00e9s rendszer\u00e1llapot",
      pipelineDesc: "Feladatok l\u00e9trehoz\u00e1sa \u00e9s VAP pipeline futtat\u00e1sa",
      agentsDesc: "\u00c1gens regisztr\u00e1ci\u00f3 \u00e9s konfigur\u00e1ci\u00f3",
      policyDesc: "Szab\u00e1lyz\u00e1si \u0151r ki\u00e9rt\u00e9kel\u0151 eszk\u00f6z",
      auditDesc: "Megv\u00e1ltoztathatatlan hash-l\u00e1nc audit napl\u00f3",
      logout: "KIL\u00c9P\u00c9S",
    },
    home: {
      bootLine: "**** OPENCLOUD CONTROL PLANE V0.6.0 ****",
      title: "VEZ\u00c9RL\u0150K\u00d6ZPONT",
      subtitle: "Hiteles\u00edtett Auton\u00f3mia Pipeline \u2014 Tervez\u00e9s, Sz\u0171r\u00e9s, V\u00e9grehajt\u00e1s, Valid\u00e1l\u00e1s, Sz\u00e1ll\u00edt\u00e1s",
      ready: "K\u00c9SZ.",
      systemStatus: "Rendszer\u00e1llapot",
      systemStatusDesc: "Val\u00f3s idej\u0171 platform eg\u00e9szs\u00e9gi mutat\u00f3k \u00e9s m\u0171k\u00f6d\u00e9si sz\u00e1ml\u00e1l\u00f3k",
      platform: "PLATFORM",
      version: "VERZI\u00d3",
      tasks: "FELADATOK",
      auditLog: "AUDIT NAPL\u00d3",
      vapTitle: "Hiteles\u00edtett Auton\u00f3mia Pipeline",
      vapDesc: "Minden feladat \u00f6t biztons\u00e1gi f\u00e1zison megy \u00e1t a sz\u00e1ll\u00edt\u00e1s el\u0151tt.",
      plan: "TERV",
      gate: "KAP.",
      exec: "V\u00c9GR.",
      valid: "VALID",
      ship: "SZ\u00c1LL.",
      planDesc: "Az AI v\u00e9grehajt\u00e1si tervet k\u00e9sz\u00edt kock\u00e1zat\u00e9rt\u00e9kel\u00e9ssel",
      gateDesc: "Szab\u00e1lyz\u00e1si \u0151r\u00f6k ellen\u0151rzik az injekci\u00f3t, PII-t \u00e9s korl\u00e1tokat",
      execDesc: "Az \u00e1gens a j\u00f3v\u00e1hagyott tervet v\u00e9dett k\u00f6rnyezetben hajtja v\u00e9gre",
      validDesc: "A kimenet min\u0151s\u00e9gi \u00e9s biztons\u00e1gi felt\u00e9telek szerint \u00e9rt\u00e9kelve",
      shipDesc: "A hiteles\u00edtett eredm\u00e9ny teljes audit nyomvonallal ker\u00fcl sz\u00e1ll\u00edt\u00e1sra",
      recentTasks: "Leg\u00fajabb Feladatok",
      recentTasksDesc: "A pipeline-ba utolj\u00e1ra bek\u00fcld\u00f6tt feladatok.",
      noTasks: "NINCS FELADAT",
      noTasksHint: "Hozzon l\u00e9tre feladatot a Pipeline oldalon vagy az API-n kereszt\u00fcl",
      noTasksCmd: 'RUN "/pipeline"',
      llmTitle: "LLM Szolg\u00e1ltat\u00f3k",
      llmDesc: "Kask\u00e1d feladatv\u00e1lt\u00e1si l\u00e1nc \u00e1llapota. 30 m\u00e1sodpercenk\u00e9nt friss\u00fcl.",
      allGo: "\u25cf MINDEN RENDSZER OK",
      degraded: "\u25b2 KORL\u00c1TOZOTT",
      online: "ONLINE",
      calls: "H\u00edv\u00e1sok",
      latency: "Latencia",
      errors: "Hib\u00e1k",
      loading: "SZOLG\u00c1LTAT\u00d3I \u00c1LLAPOT BET\u00d6LT\u00c9SE...",
      unavailable: "\u00c1LLAPOT NEM EL\u00c9RHET\u0150",
    },
    pipeline: {
      title: "PIPELINE",
      subtitle: "Hozzon l\u00e9tre feladatokat \u00e9s futtassa azokat a Hiteles\u00edtett Auton\u00f3mia Pipeline-on",
      newTask: "\u00daj Feladat",
      newTaskDesc: "Defini\u00e1ljon egy feladatot n\u00e9vvel, le\u00edr\u00e1ssal, \u00e1gens t\u00edpussal \u00e9s kock\u00e1zati szinttel.",
      taskName: "Feladat neve",
      taskDescription: "Le\u00edr\u00e1s (mit kell el\u00e9rnie az \u00e1gensnek?)",
      agentType: "\u00c1gens t\u00edpus",
      riskLevel: "Kock\u00e1zati szint",
      riskLow: "Alacsony kock\u00e1zat",
      riskMedium: "K\u00f6zepes kock\u00e1zat",
      riskHigh: "Magas kock\u00e1zat",
      riskCritical: "Kritikus kock\u00e1zat",
      create: "L\u00c9TREHOZ\u00c1S",
      creating: "L\u00c9TREHOZ\u00c1S...",
      livePipeline: "\u00c9l\u0151 Pipeline",
      liveDesc: "Az akt\u00edv feladat val\u00f3s idej\u0171 el\u0151rehalad\u00e1sa WebSocket-en kereszt\u00fcl.",
      connected: "CSATLAKOZVA",
      disconnected: "LECSATLAKOZVA",
      complete: "PIPELINE K\u00c9SZ",
      failed: "PIPELINE HIBA",
      allTasks: "\u00d6sszes Feladat",
      allTasksDesc: "A feladatok teljes el\u0151zm\u00e9nye.",
      noTasks: "M\u00e9g nincsenek feladatok.",
      noTasksHint: "Hozzon l\u00e9tre egyet fent a kezd\u00e9shez.",
      noTasksCmd: 'RUN "/pipeline"',
    },
    agents: {
      title: "\u00c1GENSEK",
      subtitle: "Aut\u00f3n\u00f3m \u00e1gensek regisztr\u00e1l\u00e1sa \u00e9s kezel\u00e9se a pipeline-ban",
      register: "REGISZTR\u00c1CI\u00d3",
      cancel: "M\u00c9GSES",
      registerNew: "\u00daj \u00c1gens Regisztr\u00e1l\u00e1sa",
      registerNewDesc: "Defini\u00e1ljon egy \u00e1genst egyedi t\u00edpusazonos\u00edt\u00f3val, megjelen\u00edt\u00e9si n\u00e9vvel \u00e9s k\u00e9pess\u00e9gekkel.",
      typePlaceholder: "\u00c1gens t\u00edpus (pl. code-reviewer)",
      typeHint: "Egyedi slug az API h\u00edv\u00e1sokhoz \u00e9s \u00fatv\u00e1laszt\u00e1shoz",
      namePlaceholder: "Megjelen\u00edt\u00e9si n\u00e9v",
      nameHint: "A m\u0171szerfalon megjelen\u0151 c\u00edmke",
      capsPlaceholder: "K\u00e9pess\u00e9gek (vessz\u0151vel elv\u00e1lasztva)",
      capsHint: "pl. code-analysis, pr-review, security-scan",
      maxConcurrent: "Max. p\u00e1rhuzamos",
      maxConcurrentHint: "P\u00e1rhuzamos v\u00e9grehajt\u00e1si korl\u00e1t",
      timeout: "Id\u0151korl\u00e1t (mp)",
      timeoutHint: "Max. v\u00e9grehajt\u00e1si id\u0151 feladatonk\u00e9nt",
      noAgents: "NINCS REGISZTR\u00c1LT \u00c1GENS",
      noAgentsHint: "Regisztr\u00e1ljon egy \u00e1genst a pipeline haszn\u00e1lat\u00e1hoz",
      concurrency: "P\u00c1RHUZAMOSS\u00c1G",
      unregister: "T\u00d6RL\u00c9S",
      confirm: "MEGER\u0150S\u00cdT?",
      registering: "REGISZTR\u00c1CI\u00d3...",
    },
    policy: {
      title: "SZAB\u00c1LY TESZTEL\u0150",
      subtitle: "Tartalom tesztel\u00e9se az OCCP szab\u00e1ly\u0151r\u00f6k ellen \u2014 PII, prompt injekci\u00f3, er\u0151forr\u00e1s korl\u00e1tok",
      safePrompt: "BIZTONS\u00c1GOS PROMPT",
      injection: "INJEKCI\u00d3",
      piiContent: "PII TARTALOM",
      presetsDesc: "Gyors teszt forgatmk\u00f6nyvek bet\u00f6lt\u00e9se",
      placeholder: "Adja meg a ki\u00e9rt\u00e9kelend\u0151 tartalmat...",
      evaluate: "KI\u00c9RT\u00c9KEL\u00c9S",
      evaluating: "KI\u00c9RT\u00c9KEL\u00c9S...",
      approved: "J\u00d3V\u00c1HAGYVA",
      rejected: "ELUTAS\u00cdTVA",
      guardsPassed: "\u0151r \u00e1tment",
      inputDesc: "Illessze be vagy \u00edrja be a tartalmat. A motor minden akt\u00edv \u0151r ellen ellen\u0151rzi.",
    },
    audit: {
      title: "AUDIT NAPL\u00d3",
      subtitle: "Manipul\u00e1ci\u00f3-biztos SHA-256 hash l\u00e1nc az \u00f6sszes pipeline m\u0171veletr\u0151l",
      entries: "bejegyz\u00e9s",
      refresh: "FRISS\u00cdT\u00c9S",
      hashChain: "HASH L\u00c1NC",
      valid: "\u00c9RV\u00c9NYES",
      broken: "T\u00d6R\u00d6TT",
      time: "ID\u0150",
      actor: "SZEREPL\u0150",
      action: "M\u0170VELET",
      task: "FELADAT",
      hash: "HASH",
      noEntries: "NINCS BEJEGYZ\u00c9S",
      loading: "AUDIT NAPL\u00d3 BET\u00d6LT\u00c9SE...",
      chainDesc: "Minden bejegyz\u00e9s kriptogr\u00e1fiailag az el\u0151z\u0151h\u00f6z k\u00f6t\u0151dik.",
    },
    common: {
      error: "HIBA",
      dismiss: "BEZ\u00c1R\u00c1S",
      runPipeline: "PIPELINE FUTTAT\u00c1SA",
      id: "AZON.",
    },
  },
};

/* ── Context ───────────────────────────────────────────── */

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: T;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (stored && translations[stored]) {
      setLocaleState(stored);
    }
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.lang = l;
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t: translations[locale] }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useT(): T {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useT must be used within I18nProvider");
  return ctx.t;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
