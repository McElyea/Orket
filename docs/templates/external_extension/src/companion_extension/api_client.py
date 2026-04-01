from __future__ import annotations

import re
from typing import Any

from .host_runtime_client import HostRuntimeClient
from .runtime_config import (
    PENDING_NEXT_TURN_KEY,
    PROFILE_CONFIG_KEY,
    SESSION_OVERRIDE_KEY,
    decode_json_object,
    encode_json_object,
    merge_nested,
    normalize_config_patch,
    resolve_preview_config,
)
from .runtime_helpers import (
    build_system_prompt,
    format_history_context,
    format_memory_rows,
    suggest_adaptive_silence_delay,
    utc_now_iso,
)

_TURN_KEY_RE = re.compile(r"^turn\.(\d{6})\.(user|assistant)$")


class CompanionApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        api_key: str = "",
        extension_id: str = "orket.companion",
    ) -> None:
        self._host = HostRuntimeClient(
            base_url,
            extension_id=extension_id,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
        )

    async def status(self) -> dict[str, Any]:
        payload = await self._host.status()
        payload.pop("extension_id", None)
        return payload

    async def models(self, *, provider: str = "ollama") -> dict[str, Any]:
        payload = await self._host.models(provider=provider)
        payload.pop("extension_id", None)
        return payload

    async def get_config(self, *, session_id: str) -> dict[str, Any]:
        config = resolve_preview_config(
            profile_defaults=await self._load_profile_defaults(),
            session_override=await self._load_session_json(session_id=session_id, key=SESSION_OVERRIDE_KEY),
            pending_next_turn=await self._load_session_json(session_id=session_id, key=PENDING_NEXT_TURN_KEY),
            include_pending_next_turn=True,
        )
        return {"ok": True, "session_id": session_id, "config": config.model_dump(mode="json", exclude_none=True)}

    async def update_config(self, *, session_id: str, scope: str, patch: dict[str, Any]) -> dict[str, Any]:
        normalized_scope = str(scope or "").strip()
        if normalized_scope not in {"profile", "session", "next_turn"}:
            raise ValueError(f"E_COMPANION_CONFIG_SCOPE_INVALID: {normalized_scope}")
        normalized_patch = normalize_config_patch(patch)

        if normalized_scope == "profile":
            merged = merge_nested(await self._load_profile_defaults(), normalized_patch)
            resolve_preview_config(
                profile_defaults=merged,
                session_override=await self._load_session_json(session_id=session_id, key=SESSION_OVERRIDE_KEY),
                pending_next_turn=await self._load_session_json(session_id=session_id, key=PENDING_NEXT_TURN_KEY),
                include_pending_next_turn=True,
            )
            await self._host.memory_write(
                scope="profile_memory",
                key=PROFILE_CONFIG_KEY,
                value=encode_json_object(merged),
                metadata={"kind": "companion_config_profile_defaults"},
            )
        elif normalized_scope == "session":
            merged = merge_nested(
                await self._load_session_json(session_id=session_id, key=SESSION_OVERRIDE_KEY),
                normalized_patch,
            )
            resolve_preview_config(
                profile_defaults=await self._load_profile_defaults(),
                session_override=merged,
                pending_next_turn=await self._load_session_json(session_id=session_id, key=PENDING_NEXT_TURN_KEY),
                include_pending_next_turn=True,
            )
            await self._write_session_json(
                session_id=session_id,
                key=SESSION_OVERRIDE_KEY,
                payload=merged,
                kind="companion_config_session_override",
            )
        else:
            merged = merge_nested(
                await self._load_session_json(session_id=session_id, key=PENDING_NEXT_TURN_KEY),
                normalized_patch,
            )
            resolve_preview_config(
                profile_defaults=await self._load_profile_defaults(),
                session_override=await self._load_session_json(session_id=session_id, key=SESSION_OVERRIDE_KEY),
                pending_next_turn=merged,
                include_pending_next_turn=True,
            )
            await self._write_session_json(
                session_id=session_id,
                key=PENDING_NEXT_TURN_KEY,
                payload=merged,
                kind="companion_config_next_turn_override",
            )

        return {
            "ok": True,
            "session_id": session_id,
            "scope": normalized_scope,
            "config": (await self.get_config(session_id=session_id))["config"],
        }

    async def history(self, *, session_id: str, limit: int = 50) -> dict[str, Any]:
        rows = await self._session_memory_records(session_id=session_id, limit=max(200, int(limit) * 4))
        history = self._extract_history_rows(rows)
        bounded_limit = max(1, min(200, int(limit)))
        return {"ok": True, "session_id": session_id, "history": history[-bounded_limit:]}

    async def chat(
        self,
        *,
        session_id: str,
        message: str,
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        user_message = str(message or "").strip()
        if not user_message:
            raise ValueError("E_COMPANION_MESSAGE_REQUIRED")

        config = resolve_preview_config(
            profile_defaults=await self._load_profile_defaults(),
            session_override=await self._load_session_json(session_id=session_id, key=SESSION_OVERRIDE_KEY),
            pending_next_turn=await self._load_session_json(session_id=session_id, key=PENDING_NEXT_TURN_KEY),
            include_pending_next_turn=True,
        )
        session_rows = await self._session_memory_records(session_id=session_id, limit=200)
        history_rows = self._extract_history_rows(session_rows)
        memory_context = await self._build_memory_context(session_id=session_id, config=config, session_rows=session_rows)
        result = await self._host.llm_generate(
            system_prompt=build_system_prompt(
                config=config,
                memory_context=memory_context,
                history_context=format_history_context(history_rows[-6:]),
            ),
            user_message=user_message,
            max_tokens=256,
            temperature=0.2,
            provider=provider,
            model=model,
        )
        assistant_text = str(result.get("text") or "").strip() or "I could not generate a response."
        turn_id = self._next_turn_id(history_rows)
        timestamp_utc = utc_now_iso()

        if config.memory.session_memory_enabled:
            await self._host.memory_write(
                scope="session_memory",
                session_id=session_id,
                key=f"{turn_id}.user",
                value=user_message,
                metadata={"kind": "chat_input", "timestamp_utc": timestamp_utc},
            )
            await self._host.memory_write(
                scope="session_memory",
                session_id=session_id,
                key=f"{turn_id}.assistant",
                value=assistant_text,
                metadata={"kind": "chat_output", "timestamp_utc": timestamp_utc},
            )
        if config.memory.episodic_memory_enabled:
            await self._host.memory_write(
                scope="episodic_memory",
                session_id=session_id,
                key=f"{turn_id}.summary",
                value=assistant_text,
                metadata={"kind": "episodic_turn", "timestamp_utc": timestamp_utc},
            )
        await self._write_session_json(
            session_id=session_id,
            key=PENDING_NEXT_TURN_KEY,
            payload={},
            kind="companion_config_next_turn_override",
        )
        status = await self.status()
        return {
            "ok": True,
            "session_id": session_id,
            "turn_id": turn_id,
            "message": assistant_text,
            "model": str(result.get("model") or ""),
            "latency_ms": int(result.get("latency_ms") or 0),
            "config": config.model_dump(mode="json", exclude_none=True),
            "text_only_degraded": not bool(status.get("stt_available")),
        }

    async def clear_session_memory(self, *, session_id: str) -> dict[str, Any]:
        deleted_session = await self._host.memory_clear(scope="session_memory", session_id=session_id)
        deleted_episodic = await self._host.memory_clear(scope="episodic_memory", session_id=session_id)
        return {
            "ok": True,
            "session_id": session_id,
            "deleted_records": int(deleted_session.get("deleted_records") or 0)
            + int(deleted_episodic.get("deleted_records") or 0),
            "deleted_episodic_records": int(deleted_episodic.get("deleted_records") or 0),
        }

    async def voice_state(self) -> dict[str, Any]:
        payload = await self._host.voice_state()
        payload.pop("extension_id", None)
        return payload

    async def voice_voices(self) -> dict[str, Any]:
        payload = await self._host.voice_voices()
        payload.pop("extension_id", None)
        return payload

    async def voice_control(self, *, command: str, silence_delay_sec: float | None = None) -> dict[str, Any]:
        payload = await self._host.voice_control(command=command, silence_delay_sec=silence_delay_sec)
        payload.pop("extension_id", None)
        return payload

    async def voice_transcribe(
        self,
        *,
        audio_b64: str,
        mime_type: str = "audio/wav",
        language_hint: str = "",
    ) -> dict[str, Any]:
        payload = await self._host.voice_transcribe(
            audio_b64=audio_b64,
            mime_type=mime_type,
            language_hint=language_hint,
        )
        payload.pop("extension_id", None)
        return payload

    async def voice_synthesize(
        self,
        *,
        text: str,
        voice_id: str = "",
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> dict[str, Any]:
        payload = await self._host.voice_synthesize(
            text=text,
            voice_id=voice_id,
            emotion_hint=emotion_hint,
            speed=speed,
        )
        payload.pop("extension_id", None)
        return payload

    async def voice_cadence_suggest(self, *, session_id: str, text: str) -> dict[str, Any]:
        utterance = str(text or "").strip()
        if not utterance:
            raise ValueError("E_COMPANION_CADENCE_TEXT_REQUIRED")
        voice = (await self.get_config(session_id=session_id))["config"]["voice"]
        if not bool(voice.get("adaptive_cadence_enabled")):
            return {
                "ok": True,
                "session_id": session_id,
                "adaptive_cadence_enabled": False,
                "source": "manual",
                "suggested_silence_delay_sec": float(voice.get("silence_delay_sec") or 0.0),
                "input_words": max(1, len(utterance.split())),
            }
        suggested, words = suggest_adaptive_silence_delay(
            text=utterance,
            silence_delay_min_sec=float(voice.get("silence_delay_min_sec") or 0.2),
            silence_delay_max_sec=float(voice.get("silence_delay_max_sec") or 6.0),
            adaptive_cadence_min_sec=float(voice.get("adaptive_cadence_min_sec") or 0.4),
            adaptive_cadence_max_sec=float(voice.get("adaptive_cadence_max_sec") or 4.0),
        )
        return {
            "ok": True,
            "session_id": session_id,
            "adaptive_cadence_enabled": True,
            "source": "adaptive",
            "suggested_silence_delay_sec": suggested,
            "input_words": words,
        }

    async def _build_memory_context(self, *, session_id: str, config: Any, session_rows: list[dict[str, Any]]) -> str:
        snippets: list[str] = []
        if config.memory.session_memory_enabled:
            visible_session_rows = [
                row for row in session_rows if not str(row.get("key") or "").startswith("companion_runtime.")
            ]
            snippets.extend(format_memory_rows(visible_session_rows[:8], prefix="session"))
        if config.memory.profile_memory_enabled:
            profile_payload = await self._host.memory_query(scope="profile_memory", query="", limit=50)
            profile_rows = [
                row
                for row in list(profile_payload.get("records") or [])
                if str(row.get("key") or "") != PROFILE_CONFIG_KEY
            ]
            snippets.extend(format_memory_rows(profile_rows[:8], prefix="profile"))
        if config.memory.episodic_memory_enabled:
            episodic_payload = await self._host.memory_query(
                scope="episodic_memory",
                session_id=session_id,
                query="",
                limit=6,
            )
            snippets.extend(format_memory_rows(list(episodic_payload.get("records") or []), prefix="episodic"))
        return "\n".join(snippets)

    async def _load_profile_defaults(self) -> dict[str, Any]:
        payload = await self._host.memory_query(scope="profile_memory", query=f"key:{PROFILE_CONFIG_KEY}", limit=1)
        rows = list(payload.get("records") or [])
        if not rows:
            return {}
        return decode_json_object(str(rows[0].get("value") or ""))

    async def _load_session_json(self, *, session_id: str, key: str) -> dict[str, Any]:
        payload = await self._host.memory_query(scope="session_memory", session_id=session_id, query=key, limit=20)
        for row in list(payload.get("records") or []):
            if str(row.get("key") or "").strip() == key:
                return decode_json_object(str(row.get("value") or ""))
        return {}

    async def _write_session_json(self, *, session_id: str, key: str, payload: dict[str, Any], kind: str) -> None:
        await self._host.memory_write(
            scope="session_memory",
            session_id=session_id,
            key=key,
            value=encode_json_object(payload),
            metadata={"kind": kind},
        )

    async def _session_memory_records(self, *, session_id: str, limit: int) -> list[dict[str, Any]]:
        payload = await self._host.memory_query(scope="session_memory", session_id=session_id, query="", limit=limit)
        return list(payload.get("records") or [])

    @staticmethod
    def _extract_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[int, dict[str, dict[str, Any]]] = {}
        for row in rows:
            match = _TURN_KEY_RE.fullmatch(str(row.get("key") or "").strip())
            if match is None:
                continue
            turn_index = int(match.group(1))
            role = "user" if match.group(2) == "user" else "assistant"
            grouped.setdefault(turn_index, {})[role] = {
                "role": role,
                "content": str(row.get("value") or ""),
                "timestamp_utc": str(row.get("updated_at") or row.get("created_at") or ""),
            }

        history: list[dict[str, Any]] = []
        for turn_index in sorted(grouped):
            turn = grouped[turn_index]
            if "user" in turn:
                history.append(turn["user"])
            if "assistant" in turn:
                history.append(turn["assistant"])
        return history

    @staticmethod
    def _next_turn_id(history_rows: list[dict[str, Any]]) -> str:
        assistant_turns = max(0, len([row for row in history_rows if str(row.get("role") or "") == "assistant"]))
        return f"turn.{assistant_turns + 1:06d}"
