"""WebSocket entry point for the character conversation engine.

Trimmed from upstream open_llm_vtuber's websocket_handler.py: only the message types
actually used by this integration's frontend (live2d-frontend in pet mode, no sidebar)
are handled — no group chat, vision/pose, MCP, or character-switching. See the migration
plan for the full rationale.

Each connection gets its own ServiceContext (and therefore its own agent memory — see
service_context.py's docstring for the upstream bug this fixes); the heavy ASR/TTS engines
and Live2D model are loaded once, lazily, on the first connection and shared by reference
after that.
"""

import asyncio
import json
import uuid

import numpy as np
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from loguru import logger

from .engine.character import build_config
from .engine.chat_history import create_new_history, delete_history, get_history, get_history_list
from .engine.conversation_handler import handle_conversation_trigger, handle_individual_interrupt
from .engine.message_handler import message_handler
from .engine.paths import BACKGROUNDS_DIR
from .engine.service_context import ServiceContext

_default_context: ServiceContext | None = None
_default_context_lock = asyncio.Lock()


async def _get_default_context() -> ServiceContext:
    """Build the shared ASR/TTS/Live2D/agent-template context once, lazily."""
    global _default_context
    if _default_context is not None:
        return _default_context

    async with _default_context_lock:
        if _default_context is None:
            ctx = ServiceContext()
            await ctx.load_from_config(build_config())
            _default_context = ctx
    return _default_context


class Live2DConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.client_uid = str(uuid.uuid4())
        self.received_audio_buffer = {self.client_uid: np.array([], dtype=np.float32)}
        self.current_conversation_tasks = {}
        self.context: ServiceContext | None = None

        try:
            default_context = await _get_default_context()
            self.context = ServiceContext()
            await self.context.load_cache(
                config=default_context.config,
                system_config=default_context.system_config,
                character_config=default_context.character_config,
                live2d_model=default_context.live2d_model,
                asr_engine=default_context.asr_engine,
                tts_engine=default_context.tts_engine,
                client_uid=self.client_uid,
            )
            await self._send_text(json.dumps({"type": "full-text", "text": "Connection established"}))
            await self._send_set_model_and_conf()
            await self._send_text(json.dumps({"type": "control", "text": "start-mic"}))

            # The browser may not have subscribed to messages yet when the socket opens.
            await asyncio.sleep(0.5)
            await self._send_set_model_and_conf()

            logger.info(f"Connection established for client {self.client_uid}")
        except Exception as e:
            logger.error(f"Failed to initialize connection for client {self.client_uid}: {e}")
            await self.close()
            raise

    async def disconnect(self, code):
        task = self.current_conversation_tasks.get(self.client_uid)
        if task and not task.done():
            task.cancel()
        if self.context:
            await self.context.close()
        message_handler.cleanup_client(self.client_uid)
        logger.info(f"Client {self.client_uid} disconnected")

    async def _send_text(self, text: str) -> None:
        await self.send(text_data=text)

    async def _send_set_model_and_conf(self) -> None:
        await self._send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": self.context.live2d_model.model_info,
                    "conf_name": self.context.character_config.conf_name,
                    "conf_uid": self.context.character_config.conf_uid,
                    "client_uid": self.client_uid,
                }
            )
        )

    async def receive_json(self, content, **kwargs):
        message_handler.handle_message(self.client_uid, content)

        msg_type = content.get("type")
        try:
            if msg_type in ("text-input", "mic-audio-end"):
                await handle_conversation_trigger(
                    msg_type=msg_type,
                    data=content,
                    client_uid=self.client_uid,
                    context=self.context,
                    websocket_send=self._send_text,
                    received_data_buffers=self.received_audio_buffer,
                    current_conversation_tasks=self.current_conversation_tasks,
                )
            elif msg_type == "mic-audio-data":
                audio_data = content.get("audio", [])
                if audio_data:
                    self.received_audio_buffer[self.client_uid] = np.append(
                        self.received_audio_buffer[self.client_uid],
                        np.array(audio_data, dtype=np.float32),
                    )
            elif msg_type == "interrupt-signal":
                await handle_individual_interrupt(
                    client_uid=self.client_uid,
                    current_conversation_tasks=self.current_conversation_tasks,
                    context=self.context,
                    heard_response=content.get("text", ""),
                )
            elif msg_type == "fetch-history-list":
                histories = await asyncio.to_thread(get_history_list, self.context.character_config.conf_uid)
                await self._send_text(json.dumps({"type": "history-list", "histories": histories}))
            elif msg_type == "fetch-and-set-history":
                await self._handle_fetch_history(content)
            elif msg_type == "create-new-history":
                await self._handle_create_history()
            elif msg_type == "delete-history":
                await self._handle_delete_history(content)
            elif msg_type == "fetch-configs":
                await self._send_text(
                    json.dumps(
                        {
                            "type": "config-files",
                            "configs": [{"filename": "conf.yaml", "name": self.context.character_config.conf_name}],
                        }
                    )
                )
            elif msg_type == "fetch-backgrounds":
                bg_files = [p.name for p in BACKGROUNDS_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif")]
                await self._send_text(json.dumps({"type": "background-files", "files": bg_files}))
            elif msg_type == "request-init-config":
                await self._send_set_model_and_conf()
            elif msg_type == "heartbeat":
                await self._send_text(json.dumps({"type": "heartbeat-ack"}))
            elif msg_type == "frontend-playback-complete":
                pass  # already resolved via message_handler.handle_message() above
            else:
                logger.warning(f"Unhandled message type: {msg_type}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self._send_text(json.dumps({"type": "error", "message": str(e)}))

    async def _handle_fetch_history(self, content: dict) -> None:
        history_uid = content.get("history_uid")
        if not history_uid:
            return
        self.context.history_uid = history_uid
        await asyncio.to_thread(
            self.context.agent_engine.set_memory_from_history,
            self.context.character_config.conf_uid,
            history_uid,
        )
        messages = await asyncio.to_thread(get_history, self.context.character_config.conf_uid, history_uid)
        messages = [msg for msg in messages if msg["role"] != "system"]
        await self._send_text(json.dumps({"type": "history-data", "messages": messages}))

    async def _handle_create_history(self) -> None:
        history_uid = await asyncio.to_thread(create_new_history, self.context.character_config.conf_uid)
        if history_uid:
            self.context.history_uid = history_uid
            await asyncio.to_thread(
                self.context.agent_engine.set_memory_from_history,
                self.context.character_config.conf_uid,
                history_uid,
            )
            await self._send_text(json.dumps({"type": "new-history-created", "history_uid": history_uid}))

    async def _handle_delete_history(self, content: dict) -> None:
        history_uid = content.get("history_uid")
        if not history_uid:
            return
        success = await asyncio.to_thread(delete_history, self.context.character_config.conf_uid, history_uid)
        await self._send_text(json.dumps({"type": "history-deleted", "success": success, "history_uid": history_uid}))
        if history_uid == self.context.history_uid:
            self.context.history_uid = None
