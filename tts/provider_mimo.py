# -*- coding: utf-8 -*-
"""MiMo V2.5 TTS Provider — OpenAI-compatible chat completions format.

Supported models:
  - mimo-v2.5-tts          : Built-in voices, singing mode, style tags
  - mimo-v2.5-tts-voicedesign : Voice design via text description
  - mimo-v2.5-tts-voiceclone  : Voice cloning from audio samples
  - mimo-v2-tts            : Legacy model
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

from ..core.constants import MIMO_EMOTION_STYLE_MAP, MIMO_MODELS
from ..utils.audio import validate_audio_file


logger = logging.getLogger(__name__)

_VOICED_MODEL = "mimo-v2.5-tts-voicedesign"
_CLONE_MODEL = "mimo-v2.5-tts-voiceclone"


class MiMoTTS:
    """MiMo V2.5 TTS provider using OpenAI-compatible chat completions endpoint.

    Key differences from other providers:
    - Endpoint: ``/v1/chat/completions``
    - Auth header: ``api-key: <key>`` (NOT ``Authorization: Bearer``)
    - Target text goes in ``role: assistant`` message
    - Style/emotion instructions go in ``role: user`` message
    - Response: ``choices[0].message.audio.data`` (base64-encoded audio)
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        *,
        fmt: str = "wav",
        speed: float = 1.0,
        voice_id: str = "",
        emotion: str = "neutral",
        voice_description: str = "",
        optimize_text_preview: bool = False,
        clone_audio_path: str = "",
        style_instruction: str = "",
        singing_mode: bool = False,
        max_retries: int = 2,
        timeout: int = 30,
    ):
        self.api_url = (api_url or "https://api.xiaomimimo.com/v1").rstrip("/")
        self.api_key = (api_key or "").strip()
        self.model = model or "mimo-v2.5-tts"
        self.format = (fmt or "wav").lower()
        self.speed = float(speed)
        self.voice_id = voice_id or "mimo_default"
        self.default_emotion = (emotion or "neutral").lower()
        self.voice_description = (voice_description or "").strip()
        self.optimize_text_preview = bool(optimize_text_preview)
        self.clone_audio_path = (clone_audio_path or "").strip()
        self.style_instruction = (style_instruction or "").strip()
        self.singing_mode = bool(singing_mode)
        self.max_retries = max(0, int(max_retries))
        self.timeout = max(5, int(timeout))
        self._session: Optional[aiohttp.ClientSession] = None
        self._clone_audio_cache: Optional[str] = None

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            client_timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=client_timeout)

    @staticmethod
    def _emotion_to_style(emotion: str) -> str:
        return MIMO_EMOTION_STYLE_MAP.get(
            emotion.lower(),
            MIMO_EMOTION_STYLE_MAP["neutral"],
        )

    def _resolve_user_content(self, emotion: str) -> str:
        if self.model == _VOICED_MODEL:
            return self.voice_description or "年轻女性，温柔甜美，语速适中。"
        if self.style_instruction:
            return self.style_instruction
        style = self._emotion_to_style(emotion)
        if abs(self.speed - 1.0) > 0.05:
            speed_desc = "稍快" if self.speed > 1.0 else "稍慢"
            style += f"语速{speed_desc}。"
        return style

    async def _load_clone_voice(self) -> Optional[str]:
        if self._clone_audio_cache is not None:
            return self._clone_audio_cache or None

        if not self.clone_audio_path:
            return None

        path = Path(self.clone_audio_path)
        if not path.is_absolute():
            path = Path(__file__).parent.parent / path

        if not path.exists() or not path.is_file():
            logger.warning("MiMoTTS: clone audio file not found: %s", path)
            return None

        try:
            data = await asyncio.to_thread(path.read_bytes)
            if not data:
                return None
            suffix = path.suffix.lower()
            mime = "audio/wav" if suffix == ".wav" else "audio/mpeg"
            b64 = base64.b64encode(data).decode("ascii")
            result = f"data:{mime};base64,{b64}"
            self._clone_audio_cache = result
            return result
        except Exception as e:
            logger.error("MiMoTTS: failed to load clone audio: %s", e)
            return None

    def _build_payload(
        self,
        text: str,
        *,
        voice: str,
        emotion: str,
    ) -> Dict[str, Any]:
        user_content = self._resolve_user_content(emotion)

        assistant_content = text
        if self.singing_mode and self.model != _VOICED_MODEL:
            assistant_content = f"(唱歌){text}"

        messages = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "audio": {
                "format": self.format,
            },
            "stream": False,
        }

        if self.model == _VOICED_MODEL:
            if self.optimize_text_preview:
                payload["audio"]["optimize_text_preview"] = True
        elif self.model == _CLONE_MODEL:
            if voice:
                payload["audio"]["voice"] = voice
        else:
            payload["audio"]["voice"] = voice

        return payload

    @staticmethod
    async def _write_bytes(path: Path, content: bytes) -> None:
        def _write() -> None:
            with open(path, "wb") as f:
                f.write(content)

        await asyncio.to_thread(_write)

    async def synth(
        self,
        text: str,
        voice: str,
        out_dir: Path,
        speed: Optional[float] = None,
        *,
        emotion: Optional[str] = None,
    ) -> Optional[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key:
            logger.error("MiMoTTS: missing api key")
            return None

        effective_voice = voice or self.voice_id
        effective_emotion = (emotion or self.default_emotion or "neutral").lower()

        if self.model == _CLONE_MODEL and self.clone_audio_path:
            clone_voice = await self._load_clone_voice()
            if clone_voice:
                effective_voice = clone_voice

        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "text": text,
                    "voice": effective_voice[:128],
                    "emotion": effective_emotion,
                    "model": self.model,
                    "fmt": self.format,
                    "style": self.style_instruction,
                    "singing": self.singing_mode,
                },
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()[:16]

        out_path = out_dir / f"{cache_key}.{self.format}"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path

        payload = self._build_payload(
            text,
            voice=effective_voice,
            emotion=effective_emotion,
        )

        url = f"{self.api_url}/chat/completions"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        await self._ensure_session()
        last_error: Optional[str] = None
        backoff = 1.0

        for attempt in range(1, self.max_retries + 2):
            try:
                assert self._session is not None
                async with self._session.post(
                    url,
                    headers=headers,
                    json=payload,
                ) as resp:
                    if 200 <= resp.status < 300:
                        data = await resp.json(content_type=None)

                        try:
                            audio_b64 = data["choices"][0]["message"]["audio"]["data"]
                        except (KeyError, IndexError, TypeError) as exc:
                            last_error = f"unexpected response structure: {exc}"
                            logger.error("MiMoTTS: %s", last_error)
                            break

                        raw = base64.b64decode(audio_b64)
                        if not raw:
                            last_error = "empty audio data after base64 decode"
                            break

                        await self._write_bytes(out_path, raw)

                        if not await validate_audio_file(out_path, expected_format=self.format):
                            last_error = "audio file validation failed"
                            break

                        logger.info(
                            "MiMoTTS: synth ok model=%s voice=%s emotion=%s size=%d",
                            self.model,
                            effective_voice[:32] if len(effective_voice) > 32 else effective_voice,
                            effective_emotion,
                            len(raw),
                        )
                        return out_path

                    try:
                        err = await resp.json(content_type=None)
                    except Exception:
                        err = await resp.text()
                    last_error = f"http {resp.status}: {err}"

                    if resp.status in (429,) or 500 <= resp.status < 600:
                        if attempt <= self.max_retries:
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2, 8)
                            continue
                    break

            except Exception as e:
                last_error = str(e)
                if attempt <= self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 8)
                    continue
                break

        try:
            if out_path.exists() and out_path.stat().st_size == 0:
                out_path.unlink()
        except Exception:
            pass

        logger.error("MiMoTTS synth failed: %s", last_error)
        return None
