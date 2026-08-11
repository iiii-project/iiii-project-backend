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

from .engine.agent.output_types import Actions, DisplayText
from .engine.character import build_config
from .engine.chat_history import create_new_history, delete_history, get_history, get_history_list, store_message
from .engine.conversation import TTSTaskManager, finalize_conversation_turn, send_conversation_start_signals
from .engine.conversation_handler import handle_conversation_trigger, handle_individual_interrupt
from .engine.message_handler import message_handler
from .engine.paths import BACKGROUNDS_DIR
from .engine.service_context import ServiceContext
from .engine.utils.sentence_divider import segment_text_by_pysbd

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
            elif msg_type == "speak-text":
                # 必須包成背景 task（跟 handle_conversation_trigger 一樣）：_handle_speak_text
                # 會等待 client 回傳 frontend-playback-complete，若直接 await 在這裡會卡死整個
                # receive_json 迴圈，導致那則回傳訊息永遠等不到被處理的機會（實測踩過一次）。
                self.current_conversation_tasks[self.client_uid] = asyncio.create_task(
                    self._handle_speak_text(content.get("text", ""))
                )
            elif msg_type == "remember-context":
                # 靜默寫入記憶：不經 TTS、不進聊天記錄，純粹讓角色「知道」某件事
                # （目前用在小夥伴開場白只講招呼語，但仍需要知道解籤全文以便答追問）。
                # silent=True：這段內容從沒被講出來過，之後若使用者打斷角色說話，
                # handle_interrupt() 不能把這筆記憶誤當成「被打斷的發言」蓋掉。
                # 純同步操作、沒有任何 await 會卡住，不需要像 speak-text 那樣包成背景 task。
                if self.context and self.context.agent_engine:
                    self.context.agent_engine.remember(content.get("text", ""), role="assistant", silent=True)
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

    async def _handle_speak_text(self, text: str) -> None:
        """Speak a piece of text (e.g. a fortune reading) directly via TTS, bypassing the
        LLM entirely — the words must be exactly what ai_service already generated, not a
        paraphrase. The text is still remembered in the agent's memory (and chat history) so
        a follow-up question in the normal chat flow has the right context."""
        text = (text or "").strip()
        if not text or not self.context:
            return

        character_name = self.context.character_config.character_name
        avatar = self.context.character_config.avatar

        # 記憶跟歷史記錄要在排 TTS 之前就先寫入，不能等 finalize_conversation_turn 裡等
        # frontend-playback-complete 那段跑完——播放要等好幾秒真實時間，使用者的追問很可能
        # 在那之前就送到，若記憶還沒寫入，追問會問不到剛剛念了什麼（實測踩過一次）。
        if self.context.agent_engine:
            self.context.agent_engine.remember(text, role="assistant")
        if self.context.history_uid:
            await asyncio.to_thread(
                store_message,
                conf_uid=self.context.character_config.conf_uid,
                history_uid=self.context.history_uid,
                role="ai",
                content=text,
                name=character_name,
                avatar=avatar,
            )

        tts_manager = TTSTaskManager()
        await send_conversation_start_signals(self._send_text)

        sentences, remaining = segment_text_by_pysbd(text)
        if remaining:
            sentences.append(remaining)

        for sentence in sentences:
            await tts_manager.speak(
                tts_text=sentence,
                display_text=DisplayText(text=sentence, name=character_name, avatar=avatar),
                actions=Actions(),
                live2d_model=self.context.live2d_model,
                tts_engine=self.context.tts_engine,
                websocket_send=self._send_text,
            )

        await finalize_conversation_turn(tts_manager, self._send_text, self.client_uid)

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
