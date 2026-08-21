"""One conversation turn: user input -> LLM (streamed) -> TTS -> WebSocket payloads.

Merged and trimmed from upstream open_llm_vtuber's conversations/{single_conversation,
conversation_utils,tts_manager}.py. Dropped: group/broadcast conversation support, vision
context injection, MCP tool_call_status events, and the AudioOutput branch (this agent's
`chat()` only ever yields SentenceOutput — see agent/agents/basic_memory_agent.py) — none
of that is reachable in this single-user, text/voice-only integration.

`websocket_send` is just `Callable[[str], Awaitable[None]]` throughout — a Channels
consumer supplies e.g. `lambda text: self.send(text_data=text)`.
"""

import asyncio
import json
import random
import re
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

import numpy as np
from loguru import logger

from .agent.input_types import BatchInput, TextData, TextSource
from .agent.output_types import Actions, DisplayText, SentenceOutput
from .asr.asr_interface import ASRInterface
from .chat_history import store_message
from .live2d_model import Live2dModel
from .message_handler import message_handler
from .service_context import ServiceContext
from .tts.tts_interface import TTSInterface
from .utils.stream_audio import prepare_audio_payload

WebSocketSend = Callable[[str], Awaitable[None]]

EMOJI_LIST = ["🐶", "🐱", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐧", "🦆", "🦉", "🐺", "🦄", "🌸", "⭐️", "🔥"]


def create_batch_input(input_text: str, from_name: str, metadata: Optional[Dict[str, Any]] = None) -> BatchInput:
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content=input_text, from_name=from_name)],
        images=None,
        metadata=metadata,
    )


async def process_user_input(user_input: Union[str, np.ndarray], asr_engine: Optional[ASRInterface], websocket_send: WebSocketSend) -> str:
    if isinstance(user_input, np.ndarray):
        if asr_engine is None:
            # ASR 模型缺失/載入失敗時 service_context.init_asr 會把這個設成 None
            # (優雅降級,見該檔案),這裡要接住,不然語音輸入會讓整個對話任務炸掉。
            await websocket_send(json.dumps({
                "type": "error",
                "message": "語音辨識目前無法使用,請改用文字輸入。",
            }))
            return ""
        logger.info("Transcribing audio input...")
        input_text = await asr_engine.async_transcribe_np(user_input)
        await websocket_send(json.dumps({"type": "user-input-transcription", "text": input_text}))
        return input_text
    return user_input


async def handle_sentence_output(
    output: SentenceOutput,
    live2d_model: Live2dModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: "TTSTaskManager",
) -> str:
    full_response = ""
    async for display_text, tts_text, actions in output:
        logger.debug(f"Processing output: '''{tts_text}'''...")
        full_response += display_text.text
        await tts_manager.speak(
            tts_text=tts_text,
            display_text=display_text,
            actions=actions,
            live2d_model=live2d_model,
            tts_engine=tts_engine,
            websocket_send=websocket_send,
        )
    return full_response


async def process_agent_output(
    output: SentenceOutput,
    character_config: Any,
    live2d_model: Live2dModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: "TTSTaskManager",
) -> str:
    output.display_text.name = character_config.character_name
    output.display_text.avatar = character_config.avatar
    try:
        return await handle_sentence_output(output, live2d_model, tts_engine, websocket_send, tts_manager)
    except Exception as e:
        logger.error(f"Error processing agent output: {e}")
        await websocket_send(json.dumps({"type": "error", "message": f"Error processing response: {str(e)}"}))
        return ""


async def send_conversation_start_signals(websocket_send: WebSocketSend) -> None:
    await websocket_send(json.dumps({"type": "control", "text": "conversation-chain-start"}))
    await websocket_send(json.dumps({"type": "full-text", "text": "Thinking..."}))


async def send_conversation_end_signal(websocket_send: WebSocketSend, session_emoji: str = "😊") -> None:
    await websocket_send(json.dumps({"type": "control", "text": "conversation-chain-end"}))
    logger.info(f"Conversation chain {session_emoji} completed!")


async def finalize_conversation_turn(tts_manager: "TTSTaskManager", websocket_send: WebSocketSend, client_uid: str) -> None:
    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list)
        await websocket_send(json.dumps({"type": "backend-synth-complete"}))

        response = await message_handler.wait_for_response(client_uid, "frontend-playback-complete")
        if not response:
            logger.warning(f"No playback completion response from {client_uid}")
            return

    await websocket_send(json.dumps({"type": "force-new-message"}))
    await send_conversation_end_signal(websocket_send)


async def cleanup_conversation(tts_manager: "TTSTaskManager", session_emoji: str) -> None:
    await tts_manager.aclose()
    logger.debug(f"Clearing up conversation {session_emoji}.")


class TTSTaskManager:
    """Runs TTS generation concurrently but delivers payloads to the frontend in the
    original sentence order (LLM sentences can finish TTS out of order)."""

    def __init__(self) -> None:
        self.task_list: List[asyncio.Task] = []
        self._payload_queue: asyncio.Queue = asyncio.Queue()
        self._sender_task: Optional[asyncio.Task] = None
        self._sequence_counter = 0
        self._next_sequence_to_send = 0

    async def speak(
        self,
        tts_text: str,
        display_text: DisplayText,
        actions: Optional[Actions],
        live2d_model: Live2dModel,
        tts_engine: TTSInterface,
        websocket_send: WebSocketSend,
    ) -> None:
        current_sequence = self._sequence_counter
        self._sequence_counter += 1

        if not self._sender_task or self._sender_task.done():
            self._sender_task = asyncio.create_task(self._process_payload_queue(websocket_send))

        if len(re.sub(r"[\s.,!?，。！？'\"』」）】\s]+", "", tts_text)) == 0:
            logger.debug("Empty TTS text, sending silent display payload")
            await self._send_silent_payload(display_text, actions, current_sequence)
            return

        logger.debug(f"Queuing TTS task for: '''{tts_text}''' (by {display_text.name})")
        task = asyncio.create_task(
            self._process_tts(tts_text, display_text, actions, live2d_model, tts_engine, current_sequence)
        )
        self.task_list.append(task)

    async def _process_payload_queue(self, websocket_send: WebSocketSend) -> None:
        buffered: Dict[int, Dict] = {}
        while True:
            try:
                payload, sequence_number = await self._payload_queue.get()
                buffered[sequence_number] = payload
                while self._next_sequence_to_send in buffered:
                    next_payload = buffered.pop(self._next_sequence_to_send)
                    await websocket_send(json.dumps(next_payload))
                    self._next_sequence_to_send += 1
                self._payload_queue.task_done()
            except asyncio.CancelledError:
                break

    async def _send_silent_payload(self, display_text: DisplayText, actions: Optional[Actions], sequence_number: int) -> None:
        payload = await prepare_audio_payload(audio_path=None, display_text=display_text, actions=actions)
        await self._payload_queue.put((payload, sequence_number))

    async def _process_tts(
        self,
        tts_text: str,
        display_text: DisplayText,
        actions: Optional[Actions],
        live2d_model: Live2dModel,
        tts_engine: TTSInterface,
        sequence_number: int,
    ) -> None:
        audio_file_path = None
        try:
            audio_file_path = await tts_engine.async_generate_audio(
                text=tts_text,
                file_name_no_ext=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
            )
            payload = await prepare_audio_payload(audio_path=audio_file_path, display_text=display_text, actions=actions)
            await self._payload_queue.put((payload, sequence_number))
        except Exception as e:
            logger.error(f"Error preparing audio payload: {e}")
            payload = await prepare_audio_payload(audio_path=None, display_text=display_text, actions=actions)
            await self._payload_queue.put((payload, sequence_number))
        finally:
            if audio_file_path:
                tts_engine.remove_file(audio_file_path)

    async def aclose(self) -> None:
        """取消並確實等待 `_sender_task` 結束（它是 `while True` 迴圈，不會自己跑完）。

        只呼叫 `.cancel()` 不 await 的話，事件迴圈可能還沒機會真的處理取消，
        Task 物件就被 GC 回收，會噴 `Task was destroyed but it is pending!`；
        `_handle_speak_text`（直接唸解籤結果那條路）先前完全沒清這個 task，
        每次唸完解籤就永久留一個閒置的背景 task。
        """
        self.task_list.clear()
        if self._sender_task and not self._sender_task.done():
            self._sender_task.cancel()
            try:
                await self._sender_task
            except asyncio.CancelledError:
                pass
        self._sequence_counter = 0
        self._next_sequence_to_send = 0
        self._payload_queue = asyncio.Queue()


async def process_single_conversation(
    context: ServiceContext,
    websocket_send: WebSocketSend,
    client_uid: str,
    user_input: Union[str, np.ndarray],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Process one conversation turn: transcribe (if audio) -> LLM -> TTS -> deliver."""
    tts_manager = TTSTaskManager()
    full_response = ""
    session_emoji = random.choice(EMOJI_LIST)

    try:
        await send_conversation_start_signals(websocket_send)
        logger.info(f"New Conversation Chain {session_emoji} started!")

        input_text = await process_user_input(user_input, context.asr_engine, websocket_send)

        batch_input = create_batch_input(
            input_text=input_text,
            from_name=context.character_config.human_name,
            metadata=metadata,
        )

        skip_history = bool(metadata and metadata.get("skip_history", False))
        if context.history_uid and not skip_history:
            await asyncio.to_thread(
                store_message,
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="human",
                content=input_text,
                name=context.character_config.human_name,
            )

        logger.info(f"User input: {input_text}")

        try:
            async for output_item in context.agent_engine.chat(batch_input):
                if isinstance(output_item, SentenceOutput):
                    full_response += await process_agent_output(
                        output=output_item,
                        character_config=context.character_config,
                        live2d_model=context.live2d_model,
                        tts_engine=context.tts_engine,
                        websocket_send=websocket_send,
                        tts_manager=tts_manager,
                    )
                else:
                    logger.warning(f"Unexpected item from agent chat stream: {type(output_item)}")
        except Exception as e:
            logger.exception(f"Error processing agent response stream: {e}")
            await websocket_send(json.dumps({"type": "error", "message": f"Error processing agent response: {str(e)}"}))

        if tts_manager.task_list:
            await asyncio.gather(*tts_manager.task_list)
            await websocket_send(json.dumps({"type": "backend-synth-complete"}))

        await finalize_conversation_turn(tts_manager=tts_manager, websocket_send=websocket_send, client_uid=client_uid)

        if context.history_uid and full_response:
            await asyncio.to_thread(
                store_message,
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="ai",
                content=full_response,
                name=context.character_config.character_name,
                avatar=context.character_config.avatar,
            )
            logger.info(f"AI response: {full_response}")

        return full_response

    except asyncio.CancelledError:
        logger.info(f"Conversation {session_emoji} cancelled because interrupted.")
        raise
    except Exception as e:
        logger.error(f"Error in conversation chain: {e}")
        await websocket_send(json.dumps({"type": "error", "message": f"Conversation error: {str(e)}"}))
        raise
    finally:
        await cleanup_conversation(tts_manager, session_emoji)
