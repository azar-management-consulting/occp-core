"""OpenAI Whisper API transcription client.

Converts voice audio (OGG/WebM) to text using the OpenAI
Audio Transcriptions endpoint.  Uses raw ``httpx`` — no
``openai`` package dependency required.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"


class WhisperClient:
    """Async OpenAI Whisper transcription client."""

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-1",
        language: str = "hu",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key required for Whisper transcription")
        self._api_key = api_key
        self._model = model
        self._language = language
        self._timeout = timeout

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        language: str | None = None,
    ) -> str:
        """Transcribe audio bytes via OpenAI Whisper API.

        Args:
            audio_bytes: Raw audio data (OGG Opus from Telegram).
            filename: Filename hint for the API (determines format detection).
            language: ISO-639-1 language code override (default: instance default).

        Returns:
            Transcribed text string.

        Raises:
            WhisperError: On API or network failure.
        """
        lang = language or self._language

        # Determine MIME type from filename
        mime = "audio/ogg"
        if filename.endswith(".mp3"):
            mime = "audio/mpeg"
        elif filename.endswith(".wav"):
            mime = "audio/wav"
        elif filename.endswith(".m4a"):
            mime = "audio/mp4"
        elif filename.endswith(".webm"):
            mime = "audio/webm"

        files: dict[str, Any] = {
            "file": (filename, audio_bytes, mime),
        }
        data: dict[str, str] = {
            "model": self._model,
            "language": lang,
            "response_format": "text",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    WHISPER_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    files=files,
                    data=data,
                )

            if resp.status_code != 200:
                detail = resp.text[:500]
                logger.error(
                    "Whisper API error: status=%d body=%s",
                    resp.status_code,
                    detail,
                )
                raise WhisperError(
                    f"Whisper API returned {resp.status_code}: {detail}"
                )

            text = resp.text.strip()
            logger.info(
                "Whisper transcription: %d bytes audio → %d chars text (lang=%s)",
                len(audio_bytes),
                len(text),
                lang,
            )
            return text

        except httpx.TimeoutException as exc:
            logger.error("Whisper API timeout after %.0fs", self._timeout)
            raise WhisperError(f"Whisper API timeout: {exc}") from exc
        except WhisperError:
            raise
        except Exception as exc:
            logger.error("Whisper transcription failed: %s", exc)
            raise WhisperError(f"Transcription failed: {exc}") from exc


class WhisperError(Exception):
    """Raised when Whisper transcription fails."""
