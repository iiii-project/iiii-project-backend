"""Async streaming chat completion against any OpenAI-compatible `/chat/completions` endpoint.

Trimmed from upstream open_llm_vtuber: tool/function-calling support removed (not used by
this character's conversation flow), leaving a plain text-delta stream.
"""

from typing import Any, AsyncIterator, Dict, List

from loguru import logger
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from .stateless_llm_interface import StatelessLLMInterface


class AsyncLLM(StatelessLLMInterface):
    def __init__(
        self,
        model: str,
        base_url: str,
        llm_api_key: str = "z",
        organization_id: str = "z",
        project_id: str = "z",
        temperature: float = 1.0,
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(
            base_url=base_url,
            organization=organization_id,
            project=project_id,
            api_key=llm_api_key,
        )
        logger.info(f"Initialized AsyncLLM with the parameters: {self.base_url}, {self.model}")

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        system: str = None,
        tools: List[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        stream = None
        try:
            messages_with_system = messages
            if system:
                messages_with_system = [{"role": "system", "content": system}, *messages]
            logger.debug(f"Messages: {messages_with_system}")

            stream = await self.client.chat.completions.create(
                messages=messages_with_system,
                model=self.model,
                stream=True,
                temperature=self.temperature,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                yield content or ""

        except APIConnectionError as e:
            logger.error(f"Error calling the chat endpoint: Connection error. {e.__cause__}")
            yield "Error calling the chat endpoint: Connection error. Failed to connect to the LLM API."

        except RateLimitError as e:
            logger.error(f"Error calling the chat endpoint: Rate limit exceeded: {e.response}")
            yield "Error calling the chat endpoint: Rate limit exceeded. Please try again later."

        except APIError as e:
            logger.error(f"LLM API: Error occurred: {e}")
            logger.info(f"Base URL: {self.base_url} | Model: {self.model} | temperature: {self.temperature}")
            yield "Error calling the chat endpoint: Error occurred while generating response."

        finally:
            if stream:
                await stream.close()
