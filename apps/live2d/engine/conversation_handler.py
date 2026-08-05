"""Dispatch a conversation-triggering WebSocket message into a `process_single_conversation`
task, and handle user interrupts.

Trimmed from upstream open_llm_vtuber's conversations/conversation_handler.py: the
group-conversation branch, `ai-speak-signal` (proactive speak) and vision-context injection
are removed — this is a single-user, text/voice-only integration and the current
live2d-frontend (pet mode) never sends those.
"""

import asyncio
from typing import Callable, Dict, Optional

import numpy as np
from loguru import logger

from .chat_history import store_message
from .conversation import process_single_conversation
from .service_context import ServiceContext

WebSocketSend = Callable[[str], "asyncio.Future"]


async def handle_conversation_trigger(
    msg_type: str,
    data: dict,
    client_uid: str,
    context: ServiceContext,
    websocket_send: WebSocketSend,
    received_data_buffers: Dict[str, np.ndarray],
    current_conversation_tasks: Dict[str, Optional[asyncio.Task]],
) -> Optional[asyncio.Task]:
    if msg_type == "text-input":
        user_input = data.get("text", "")
    else:  # mic-audio-end
        user_input = received_data_buffers.get(client_uid, np.array([]))
        received_data_buffers[client_uid] = np.array([])

    current_conversation_tasks[client_uid] = asyncio.create_task(
        process_single_conversation(
            context=context,
            websocket_send=websocket_send,
            client_uid=client_uid,
            user_input=user_input,
        )
    )
    return current_conversation_tasks[client_uid]


async def handle_individual_interrupt(
    client_uid: str,
    current_conversation_tasks: Dict[str, Optional[asyncio.Task]],
    context: ServiceContext,
    heard_response: str,
):
    task = current_conversation_tasks.get(client_uid)
    if task and not task.done():
        task.cancel()
        logger.info("Conversation task was successfully interrupted")

    try:
        context.agent_engine.handle_interrupt(heard_response)
    except Exception as e:
        logger.error(f"Error handling interrupt: {e}")

    if context.history_uid:
        await asyncio.to_thread(
            store_message,
            conf_uid=context.character_config.conf_uid,
            history_uid=context.history_uid,
            role="ai",
            content=heard_response,
            name=context.character_config.character_name,
            avatar=context.character_config.avatar,
        )
        await asyncio.to_thread(
            store_message,
            conf_uid=context.character_config.conf_uid,
            history_uid=context.history_uid,
            role="system",
            content="[Interrupted by user]",
        )
