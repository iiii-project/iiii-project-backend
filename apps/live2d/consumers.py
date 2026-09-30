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
import time
import uuid

import numpy as np
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from loguru import logger

from .engine.agent.output_types import Actions, DisplayText
from .engine.character import build_config
from .engine.chat_history import (
    create_new_history,
    delete_history,
    get_history,
    get_history_list,
    prune_histories,
    store_message,
)
from .engine.conversation import cleanup_conversation, TTSTaskManager, finalize_conversation_turn, send_conversation_start_signals
from .engine.conversation_handler import handle_conversation_trigger, handle_individual_interrupt
from .engine.message_handler import message_handler
from .engine.paths import BACKGROUNDS_DIR
from .engine.prompt_safety import (
    MAX_HEARD_RESPONSE_CHARS,
    MAX_SESSION_CONTEXT_CHARS,
    MAX_SPEAK_TEXT_CHARS,
    MAX_USER_INPUT_CHARS,
    sanitize_untrusted_text,
)
from .engine.service_context import ServiceContext
from .engine.utils.sentence_divider import segment_text_by_pysbd

_default_context: ServiceContext | None = None
_default_context_lock = asyncio.Lock()

# 過期聊天紀錄的清理：搭在「有人連線」這個時機順便做，但最多一小時一次，
# 不必另外跑排程，也不會每條連線都掃一次目錄。
_PRUNE_INTERVAL_SECONDS = 60 * 60
_last_prune_at = 0.0


def _schedule_history_prune(conf_uid: str) -> None:
    global _last_prune_at
    now = time.monotonic()
    if _last_prune_at and now - _last_prune_at < _PRUNE_INTERVAL_SECONDS:
        return
    _last_prune_at = now
    retention_days = getattr(settings, "LIVE2D_CHAT_HISTORY_RETENTION_DAYS", 30)
    task = asyncio.create_task(asyncio.to_thread(prune_histories, conf_uid, retention_days))
    # 保留 task 參照，避免背景 task 在跑完前被 GC 回收
    _background_tasks.add(task)
    task.add_done_callback(_on_prune_done)


_background_tasks: set[asyncio.Task] = set()


def _on_prune_done(task: asyncio.Task) -> None:
    _background_tasks.discard(task)
    if not task.cancelled() and task.exception():
        logger.error(f"History prune failed: {task.exception()}")


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
        # 聊天紀錄檔是所有連線共用同一個 conf_uid 目錄；只允許存取這條連線自己建立的，
        # 不然任何人都能列出、讀取或刪除別人的對話。
        self.owned_history_uids: set[str] = set()

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
            _schedule_history_prune(self.context.character_config.conf_uid)
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
                if msg_type == "text-input":
                    content = {**content, "text": sanitize_untrusted_text(content.get("text"), MAX_USER_INPUT_CHARS)}
                    if not content["text"]:
                        return
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
                    self._handle_speak_text(sanitize_untrusted_text(content.get("text"), MAX_SPEAK_TEXT_CHARS))
                )
            elif msg_type == "remember-context":
                # 本次求籤資料（使用者的問題＋解籤結果）：不經 TTS、不進聊天記錄。
                # 內容含使用者自己輸入的問題，屬於不可信資料——不寫成 assistant 記憶，
                # 而是清理後放進 system prompt 的資料區塊（見 prompt_safety.py）。
                if self.context and self.context.agent_engine:
                    self.context.agent_engine.set_session_context(
                        sanitize_untrusted_text(content.get("text"), MAX_SESSION_CONTEXT_CHARS)
                    )
            elif msg_type == "interrupt-signal":
                await handle_individual_interrupt(
                    client_uid=self.client_uid,
                    current_conversation_tasks=self.current_conversation_tasks,
                    context=self.context,
                    heard_response=sanitize_untrusted_text(content.get("text"), MAX_HEARD_RESPONSE_CHARS),
                )
            elif msg_type == "fetch-history-list":
                histories = await asyncio.to_thread(
                    get_history_list, self.context.character_config.conf_uid, list(self.owned_history_uids)
                )
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
        try:
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
        finally:
            await cleanup_conversation(tts_manager, "fortune-reading")

    async def _handle_fetch_history(self, content: dict) -> None:
        history_uid = content.get("history_uid")
        if not history_uid or history_uid not in self.owned_history_uids:
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
            self.owned_history_uids.add(history_uid)
            self.context.history_uid = history_uid
            # 新對話＝新的一場：上一場的求籤資料也一起清掉
            self.context.agent_engine.clear_session_context()
            await asyncio.to_thread(
                self.context.agent_engine.set_memory_from_history,
                self.context.character_config.conf_uid,
                history_uid,
            )
            await self._send_text(json.dumps({"type": "new-history-created", "history_uid": history_uid}))

    async def _handle_delete_history(self, content: dict) -> None:
        history_uid = content.get("history_uid")
        if not history_uid or history_uid not in self.owned_history_uids:
            return
        self.owned_history_uids.discard(history_uid)
        success = await asyncio.to_thread(delete_history, self.context.character_config.conf_uid, history_uid)
        await self._send_text(json.dumps({"type": "history-deleted", "success": success, "history_uid": history_uid}))
        if history_uid == self.context.history_uid:
            self.context.history_uid = None
