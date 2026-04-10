"""LLM-based intent classification for voice commands.

Classifies transcribed voice text into intent categories and maps
them to OCCP agent types for pipeline delegation.  Uses raw
``httpx`` calls to Anthropic Messages API (primary) or OpenAI
Chat Completions API (fallback).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Intent → agent_type mapping
AGENT_MAP: dict[str, str] = {
    "status_check": "general",
    "wp_audit": "general",
    "infra_overview": "general",
    "code_review": "code-reviewer",
    "security_scan": "code-reviewer",
    "seo_analysis": "general",
    "research": "general",
    "build_deploy": "general",
    "automation": "general",
    "openclaw_dispatch": "openclaw",
    "general": "general",
}

CLASSIFICATION_SYSTEM = """Te egy intent osztályozó rendszer vagy az OCCP (OpenCloud Control Plane) számára.

A felhasználó hangüzenetét transzkribált szövegként kapod. Osztályozd a szöveget az alábbi intent kategóriák egyikébe, és add vissza JSON formátumban.

## Intent kategóriák:

- `status_check` — Rendszer állapot lekérdezés ("Mi a helyzet?", "Státusz?", "Hogy állnak a dolgok?")
- `wp_audit` — WordPress audit, ellenőrzés ("WordPress audit", "Nézd át a WordPress-t", "Plugin ellenőrzés")
- `infra_overview` — Infrastruktúra áttekintés ("Infrastruktúra?", "Szerver állapot", "Erőforrások?")
- `code_review` — Kód átnézés ("Nézd át a kódot", "Code review", "Kód ellenőrzés")
- `security_scan` — Biztonsági ellenőrzés ("Biztonsági audit", "Vulnerability scan", "Biztonság?")
- `seo_analysis` — SEO elemzés ("SEO elemzés", "Keresőoptimalizálás", "SEO audit")
- `research` — Kutatás, információgyűjtés ("Kutasd ki", "Keress rá", "Mi az a...?")
- `build_deploy` — Építés, telepítés ("Építsd meg", "Deploy", "Telepítsd")
- `automation` — Automatizálás ("Automatizáld", "Workflow", "Cron job")
- `openclaw_dispatch` — OpenClaw agent küldés ("Küldj agenteket", "Agent dispatch", "OpenClaw feladat")
- `general` — Általános kérés, ami nem illik a fentiekbe

## Kockázati szint:

- `low` — Lekérdezés, olvasás, státusz (nem módosít semmit)
- `medium` — Elemzés, audit, review (olvas de nem ír)
- `high` — Módosítás, deploy, build (változtatást hajt végre)
- `critical` — Infrastruktúra módosítás, törlés, biztonsági változtatás

## Válasz formátum (KIZÁRÓLAG JSON, semmi más):

```json
{
  "intent": "status_check",
  "task_name": "Rendszer állapot ellenőrzés",
  "task_description": "A felhasználó a teljes rendszer aktuális állapotát kéri...",
  "risk_level": "low",
  "confidence": 0.95
}
```

FONTOS: Csak a JSON objektumot add vissza, semmilyen extra szöveget, magyarázatot, vagy markdown formázást."""

FALLBACK_KEYWORDS: dict[str, list[str]] = {
    "status_check": ["státusz", "állapot", "helyzet", "status", "mi van", "hogy áll"],
    "wp_audit": ["wordpress", "wp", "plugin", "theme", "elementor"],
    "infra_overview": ["szerver", "infrastruktúra", "erőforrás", "cpu", "memória", "disk"],
    "code_review": ["kód", "code", "review", "nézd át", "ellenőrizd a kódot"],
    "security_scan": ["biztonság", "security", "vulnerability", "audit", "sebezhetőség"],
    "seo_analysis": ["seo", "kereső", "google", "ranking", "optimalizálás"],
    "research": ["kutasd", "keress", "mi az", "nézz utána", "research"],
    "build_deploy": ["építsd", "deploy", "telepítsd", "build", "indítsd"],
    "automation": ["automatizáld", "workflow", "cron", "ütemezés", "schedule"],
    "openclaw_dispatch": ["agent", "dispatch", "openclaw", "küldj"],
}


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: str
    agent_type: str
    task_name: str
    task_description: str
    risk_level: str = "low"
    confidence: float = 0.0


class IntentRouter:
    """LLM-based intent classification for voice commands.

    Primary: Anthropic Claude API
    Fallback: OpenAI GPT API
    Last resort: keyword matching
    """

    def __init__(
        self,
        anthropic_api_key: str = "",
        openai_api_key: str = "",
        anthropic_model: str = "claude-sonnet-4-20250514",
        timeout: float = 15.0,
    ) -> None:
        self._anthropic_key = anthropic_api_key
        self._openai_key = openai_api_key
        self._anthropic_model = anthropic_model
        self._timeout = timeout

    async def classify(self, text: str) -> IntentResult:
        """Classify transcribed text into intent + agent_type.

        Tries Anthropic → OpenAI → keyword fallback.
        """
        # Try Anthropic first
        if self._anthropic_key:
            try:
                return await self._classify_anthropic(text)
            except Exception as exc:
                logger.warning("Anthropic intent classification failed: %s", exc)

        # Fallback to OpenAI
        if self._openai_key:
            try:
                return await self._classify_openai(text)
            except Exception as exc:
                logger.warning("OpenAI intent classification failed: %s", exc)

        # Last resort: keyword matching
        logger.info("Using keyword fallback for intent classification")
        return self._classify_keywords(text)

    async def _classify_anthropic(self, text: str) -> IntentResult:
        """Classify via Anthropic Messages API."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": self._anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._anthropic_model,
                    "max_tokens": 300,
                    "system": CLASSIFICATION_SYSTEM,
                    "messages": [
                        {"role": "user", "content": f"Osztályozd: \"{text}\""},
                    ],
                },
            )

        if resp.status_code != 200:
            raise IntentError(f"Anthropic API {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content = data.get("content", [{}])[0].get("text", "")
        return self._parse_llm_response(content, text)

    async def _classify_openai(self, text: str) -> IntentResult:
        """Classify via OpenAI Chat Completions API."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                OPENAI_URL,
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": CLASSIFICATION_SYSTEM},
                        {"role": "user", "content": f'Osztályozd: "{text}"'},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )

        if resp.status_code != 200:
            raise IntentError(f"OpenAI API {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_llm_response(content, text)

    def _parse_llm_response(self, content: str, original_text: str) -> IntentResult:
        """Parse LLM JSON response into IntentResult."""
        # Strip markdown fences if present
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            parsed: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse LLM intent JSON: %s", exc)
            return self._classify_keywords(original_text)

        intent = parsed.get("intent", "general")
        agent_type = AGENT_MAP.get(intent, "general")

        result = IntentResult(
            intent=intent,
            agent_type=agent_type,
            task_name=parsed.get("task_name", f"Voice: {original_text[:60]}"),
            task_description=parsed.get("task_description", original_text),
            risk_level=parsed.get("risk_level", "low"),
            confidence=float(parsed.get("confidence", 0.8)),
        )

        logger.info(
            "Intent classified: intent=%s agent=%s risk=%s conf=%.2f",
            result.intent,
            result.agent_type,
            result.risk_level,
            result.confidence,
        )
        return result

    def _classify_keywords(self, text: str) -> IntentResult:
        """Keyword-based fallback classification."""
        text_lower = text.lower()

        best_intent = "general"
        best_score = 0

        for intent, keywords in FALLBACK_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_intent = intent

        agent_type = AGENT_MAP.get(best_intent, "general")

        return IntentResult(
            intent=best_intent,
            agent_type=agent_type,
            task_name=f"Voice: {text[:60]}",
            task_description=text,
            risk_level="low",
            confidence=0.5 if best_score > 0 else 0.3,
        )


class IntentError(Exception):
    """Raised when intent classification fails."""
