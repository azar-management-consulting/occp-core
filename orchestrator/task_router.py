"""Intelligent task routing for the Brain.

Routes tasks to the correct agent(s) based on keyword/pattern analysis.
Deterministic, no LLM required -- pure keyword + regex scoring.

Supports Hungarian and English keywords with accent-aware matching.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Default agent when nothing matches
DEFAULT_AGENT = "eng-core"

# Minimum confidence to trust the routing decision
MIN_CONFIDENCE_THRESHOLD = 0.15


@dataclass
class RouteDecision:
    """Result of the task routing analysis."""

    primary_agent: str
    support_agents: list[str]
    risk_level: str  # low|medium|high|critical
    requires_approval: bool
    estimated_duration: str  # "5m"|"30m"|"2h"
    confidence: float  # 0.0-1.0
    matched_workflow: str | None = None

    def to_dict(self) -> dict:
        return {
            "primary_agent": self.primary_agent,
            "support_agents": self.support_agents,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "estimated_duration": self.estimated_duration,
            "confidence": round(self.confidence, 3),
            "matched_workflow": self.matched_workflow,
        }


def _normalize_hungarian(text: str) -> str:
    """Normalize Hungarian accented characters for matching.

    Converts: a/e/i/o/o/o/u/u/u (accented) -> base ASCII equivalents.
    Preserves the original casing by lowercasing first.
    """
    text = text.lower()
    # Hungarian-specific replacements (covers all common accented chars)
    replacements = {
        "\u00e1": "a",  # a
        "\u00e9": "e",  # e
        "\u00ed": "i",  # i
        "\u00f3": "o",  # o
        "\u00f6": "o",  # o
        "\u0151": "o",  # o
        "\u00fa": "u",  # u
        "\u00fc": "u",  # u
        "\u0171": "u",  # u
    }
    for accented, base in replacements.items():
        text = text.replace(accented, base)
    return text


class TaskRouter:
    """Routes tasks to agents based on content analysis.

    Uses keyword scoring + regex pattern matching to determine the best
    agent(s) for a given task. No LLM call required.
    """

    # Keyword-based routing rules (deterministic)
    ROUTING_RULES: dict[str, dict] = {
        "eng-core": {
            "keywords": [
                "python", "fastapi", "api", "backend", "bug", "test", "refactor",
                "database", "migration", "code", "typescript", "react", "next.js",
                "nextjs", "endpoint", "schema", "pytest", "unittest", "fejlesztes",
                "fejleszt", "hiba", "javitas", "kodol", "programoz", "frontend",
                "component", "sdk", "library", "module", "function", "class",
            ],
            "patterns": [
                r"fix\s+\w+", r"implement\s+\w+", r"build\s+\w+",
                r"create\s+endpoint", r"add\s+test", r"debug\s+\w+",
                r"javitsd?\s+\w+", r"epits[d]?\s+\w+",
            ],
        },
        "wp-web": {
            "keywords": [
                "wordpress", "elementor", "plugin", "wp", "landing", "oldal",
                "theme", "woocommerce", "shortcode", "widget", "hook", "filter",
                "weboldal", "honlap", "sablon", "tema", "weblap", "yoast",
                "gutenberg", "block", "bejegyzes", "poszt",
            ],
            "patterns": [
                r"wp[-_]\w+", r"elementor\s+\w+", r"wordpress\s+\w+",
                r"landing\s+page", r"oldal\w*\s+\w+",
            ],
        },
        "infra-ops": {
            "keywords": [
                "deploy", "server", "docker", "ssl", "dns", "nginx", "apache",
                "hetzner", "hostinger", "backup", "ssh", "szerver", "telepites",
                "uzemeltet", "domain", "certbot", "letsencrypt", "firewall",
                "proxy", "container", "kubernetes", "k8s", "ci", "cd", "pipeline",
                "devops", "monitoring", "log", "terraform", "ansible",
            ],
            "patterns": [
                r"\d+\.\d+\.\d+\.\d+", r"port\s+\d+",
                r"deploy\s+\w+", r"telepitsd?\s+\w+",
            ],
        },
        "design-lab": {
            "keywords": [
                "design", "ui", "ux", "layout", "vizualis", "szin", "logo",
                "kreativ", "wireframe", "mockup", "figma", "prototipus",
                "grafika", "arculat", "tipografia", "ikon", "icon", "banner",
                "illustration", "animacio", "visual", "style", "css",
            ],
            "patterns": [
                r"design\s+\w+", r"tervezd?\s+meg\s+\w+",
                r"vizualis\s+\w+", r"keszits\s+\w+\s+designt?",
            ],
        },
        "content-forge": {
            "keywords": [
                "szoveg", "copy", "cikk", "tartalom", "content", "article",
                "blog", "irj", "fogalmazz", "sales", "seo", "kulcsszo",
                "keyword", "headline", "cimsor", "newsletter", "email",
                "levelezes", "szovegezes", "hirdetesszoveg", "landolo",
            ],
            "patterns": [
                r"ir[jd]\s+\w+", r"fogalmaz[zd]\s+\w+",
                r"keszits\s+\w*(?:szoveg|cikk|tartalom)",
                r"write\s+(?:a\s+)?(?:copy|article|blog|content)",
            ],
        },
        "social-growth": {
            "keywords": [
                "facebook", "instagram", "tiktok", "social", "kampany",
                "hirdetes", "ad", "poszt", "hashtag", "linkedin", "twitter",
                "x.com", "kozossegi", "media", "reel", "story", "carousel",
                "celcsoport", "remarketing", "pixel", "lead",
            ],
            "patterns": [
                r"fb\s+\w+", r"ig\s+\w+", r"social\s+media\s+\w+",
                r"hirdess\s+\w+", r"kampany\s+\w+",
            ],
        },
        "intel-research": {
            "keywords": [
                "kutatas", "research", "versenytars", "competitor", "piaci",
                "trend", "elemzes", "analysis", "benchmark", "osszehasonlitas",
                "ertekeles", "audit", "felmereses", "statisztika", "adat",
                "jelentes", "riport", "report", "survey", "tendelek",
            ],
            "patterns": [
                r"keres[ds]\s+\w+", r"vizsgal[jd]\s+\w+",
                r"elemezd?\s+\w+", r"research\s+\w+",
                r"kutasd?\s+\w+",
            ],
        },
        "biz-strategy": {
            "keywords": [
                "ajanlat", "proposal", "uzleti", "business", "pricing",
                "arazas", "partner", "pitch", "prezentacio", "strategia",
                "strategy", "b2b", "roi", "revenue", "bevetel", "nyereseg",
                "profit", "megbizas", "szerzodes", "contract", "tender",
                "palyazat", "befektetes", "investment",
            ],
            "patterns": [
                r"ajanlat\s+\w+", r"araz[asz]+\s+\w+",
                r"keszits\s+\w*(?:ajanlat|prezentacio|pitch)",
                r"business\s+\w+",
            ],
        },
    }

    # Multi-agent workflow templates
    WORKFLOW_TEMPLATES: dict[str, list[str]] = {
        "new_landing_page": ["wp-web", "design-lab", "content-forge"],
        "deploy_and_verify": ["infra-ops", "eng-core"],
        "marketing_campaign": ["social-growth", "content-forge", "design-lab"],
        "business_proposal": ["biz-strategy", "content-forge", "intel-research"],
        "full_site_audit": ["wp-web", "eng-core", "design-lab"],
        "competitor_analysis": ["intel-research", "biz-strategy"],
        "security_hardening": ["eng-core", "infra-ops"],
    }

    # Workflow detection keywords (maps keyword -> workflow template name)
    WORKFLOW_KEYWORDS: dict[str, list[str]] = {
        "new_landing_page": [
            "landing page", "landolo oldal", "uj oldal", "new page",
            "keszits oldalt", "epits oldalt",
        ],
        "deploy_and_verify": [
            "deploy and test", "telepites es teszt", "deploy and verify",
            "elesites", "production deploy",
        ],
        "marketing_campaign": [
            "marketing kampany", "marketing campaign", "hirdetes kampany",
            "kampanyt inditok", "kampany tervezes",
        ],
        "business_proposal": [
            "uzleti ajanlat", "business proposal", "ajanlat keszites",
            "proposal keszites", "keszits ajanlatot",
        ],
        "full_site_audit": [
            "site audit", "oldal audit", "teljes audit", "weboldal audit",
            "full audit", "oldal ellenorzes",
        ],
        "competitor_analysis": [
            "versenytars elemzes", "competitor analysis", "piackutatas",
            "versenytarsat elemezd", "konkurencia",
        ],
        "security_hardening": [
            "security hardening", "biztonsagi", "hardening",
            "security audit", "vedelem", "security fix",
        ],
    }

    # Risk keywords that escalate risk level
    HIGH_RISK_KEYWORDS = {
        "production", "prod", "eles", "torol", "delete", "drop",
        "force", "reset", "rollback", "migration", "deploy",
        "dns", "ssl", "firewall", "secret", "credential", "password",
        "token", "payment", "fizetes", "szamla",
    }

    CRITICAL_RISK_KEYWORDS = {
        "force push", "drop database", "rm -rf", "delete all",
        "torolj mindent", "prod deploy", "eles deploy",
        "dns change", "dns valtoz",
    }

    def __init__(self) -> None:
        # Pre-compile regex patterns for performance
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        for agent_id, rules in self.ROUTING_RULES.items():
            self._compiled_patterns[agent_id] = [
                re.compile(p, re.IGNORECASE) for p in rules.get("patterns", [])
            ]

    def route(self, task_input: str, context: dict | None = None) -> RouteDecision:
        """Route a task to the best agent(s) based on content analysis.

        Args:
            task_input: The task description or voice command text.
            context: Optional context dict (project, previous tasks, etc.).

        Returns:
            RouteDecision with primary agent, support agents, risk, etc.
        """
        if not task_input or not task_input.strip():
            return RouteDecision(
                primary_agent=DEFAULT_AGENT,
                support_agents=[],
                risk_level="low",
                requires_approval=False,
                estimated_duration="5m",
                confidence=0.0,
            )

        # Normalize text for matching
        normalized = _normalize_hungarian(task_input)

        # Score each agent
        scores = self._score_agents(normalized)

        # Detect workflow template
        workflow = self._detect_workflow_template(normalized)

        # Determine primary agent
        if workflow:
            template_agents = self.WORKFLOW_TEMPLATES[workflow]
            primary = template_agents[0]
            support = template_agents[1:]
            # Confidence boost for workflow match
            max_score = max(scores.values()) if scores else 0.0
            confidence = min(1.0, max_score + 0.2)
        elif scores:
            sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            primary = sorted_agents[0][0]
            max_score = sorted_agents[0][1]

            # Only include support agents if they have a meaningful score
            support = [
                a for a, s in sorted_agents[1:]
                if s >= max_score * 0.4 and s >= MIN_CONFIDENCE_THRESHOLD
            ]

            confidence = max_score
        else:
            primary = DEFAULT_AGENT
            support = []
            confidence = 0.0

        # Ensure confidence is capped
        confidence = min(1.0, confidence)

        # Below threshold -> fallback
        if confidence < MIN_CONFIDENCE_THRESHOLD and not workflow:
            primary = DEFAULT_AGENT
            support = []

        # Risk assessment
        risk_level = self._assess_risk(primary, normalized)

        # Requires approval for high/critical risk
        requires_approval = risk_level in ("high", "critical")

        # Override from context
        if context and context.get("force_approval"):
            requires_approval = True

        # Duration estimate
        all_agents = [primary] + support
        estimated_duration = self._estimate_duration(all_agents)

        decision = RouteDecision(
            primary_agent=primary,
            support_agents=support,
            risk_level=risk_level,
            requires_approval=requires_approval,
            estimated_duration=estimated_duration,
            confidence=confidence,
            matched_workflow=workflow,
        )

        logger.info(
            "TaskRouter: primary=%s support=%s risk=%s confidence=%.3f workflow=%s input=%.80s",
            primary,
            support,
            risk_level,
            confidence,
            workflow,
            task_input,
        )

        return decision

    def _score_agents(self, text: str) -> dict[str, float]:
        """Score each agent based on keyword and pattern matches.

        Returns dict of agent_id -> score (0.0 to 1.0).
        """
        scores: dict[str, float] = {}
        words = set(text.split())

        for agent_id, rules in self.ROUTING_RULES.items():
            score = 0.0
            keywords = rules.get("keywords", [])

            # Keyword matches (each keyword = 0.1 weight, max from keywords = 0.7)
            keyword_hits = 0
            for kw in keywords:
                # Check both as word and as substring for multi-word keywords
                if kw in words or kw in text:
                    keyword_hits += 1

            if keywords:
                keyword_score = min(0.7, keyword_hits * 0.1)
                score += keyword_score

            # Pattern matches (each pattern = 0.15 weight, max = 0.3)
            pattern_hits = 0
            for pattern in self._compiled_patterns.get(agent_id, []):
                if pattern.search(text):
                    pattern_hits += 1

            pattern_score = min(0.3, pattern_hits * 0.15)
            score += pattern_score

            if score > 0:
                scores[agent_id] = min(1.0, score)

        return scores

    def _detect_workflow_template(self, text: str) -> Optional[str]:
        """Detect if the task matches a multi-agent workflow template.

        Returns template name or None.
        """
        best_match: str | None = None
        best_hits = 0

        for template_name, trigger_phrases in self.WORKFLOW_KEYWORDS.items():
            hits = sum(1 for phrase in trigger_phrases if phrase in text)
            if hits > best_hits:
                best_hits = hits
                best_match = template_name

        return best_match if best_hits > 0 else None

    def _assess_risk(self, primary_agent: str, text: str) -> str:
        """Assess risk level based on agent type and task content.

        Returns: "low"|"medium"|"high"|"critical"
        """
        words = set(text.split())

        # Check critical multi-word phrases first
        for phrase in self.CRITICAL_RISK_KEYWORDS:
            if phrase in text:
                return "critical"

        # Check high-risk single keywords
        high_risk_hits = sum(1 for kw in self.HIGH_RISK_KEYWORDS if kw in words or kw in text)

        # infra-ops is inherently riskier
        if primary_agent == "infra-ops":
            if high_risk_hits >= 1:
                return "high"
            return "medium"

        # eng-core with production/deploy keywords
        if primary_agent == "eng-core" and high_risk_hits >= 2:
            return "high"
        if primary_agent == "eng-core" and high_risk_hits >= 1:
            return "medium"

        # General risk escalation
        if high_risk_hits >= 3:
            return "high"
        if high_risk_hits >= 1:
            return "medium"

        return "low"

    def _estimate_duration(self, agents: list[str]) -> str:
        """Estimate task duration based on agent count and types.

        Returns: "5m"|"15m"|"30m"|"1h"|"2h"
        """
        # Base duration per agent type
        durations = {
            "eng-core": 30,
            "wp-web": 30,
            "infra-ops": 45,
            "design-lab": 20,
            "content-forge": 15,
            "social-growth": 15,
            "intel-research": 45,
            "biz-strategy": 30,
        }

        total_minutes = sum(durations.get(a, 15) for a in agents)

        if total_minutes <= 5:
            return "5m"
        if total_minutes <= 15:
            return "15m"
        if total_minutes <= 30:
            return "30m"
        if total_minutes <= 60:
            return "1h"
        return "2h"

    def format_brain_header(
        self,
        decision: RouteDecision,
        project: str = "OCCP",
    ) -> str:
        """Format the Brain's routing header for Telegram/voice output.

        Returns a formatted string with routing metadata.
        """
        support_str = ", ".join(decision.support_agents) if decision.support_agents else "-"
        risk_emoji = {
            "low": "\u2705",
            "medium": "\u26a0\ufe0f",
            "high": "\ud83d\udea8",
            "critical": "\ud83d\uded1",
        }
        risk_display = risk_emoji.get(decision.risk_level, "\u2753")

        lines = [
            "\U0001f9e0 Brian the Brain",
            f"\U0001f4cb Projekt: {project}",
            f"\U0001f916 Agent: {decision.primary_agent} + [{support_str}]",
            f"\u26a1 Kockazat: {risk_display} {decision.risk_level}",
        ]

        if decision.matched_workflow:
            lines.append(f"\U0001f504 Workflow: {decision.matched_workflow}")

        return "\n".join(lines)
