from typing import Type

from loguru import logger

from .stateless_llm.openai_compatible_llm import AsyncLLM as OpenAICompatibleLLM
from .stateless_llm.stateless_llm_interface import StatelessLLMInterface

# Every "branded" LLM config (openai_llm, gemini_llm, deepseek_llm, ...) is really just
# OpenAICompatibleConfig with a different default base_url — see config_manager/stateless_llm.py.
_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai_compatible_llm",
    "openai_llm",
    "gemini_llm",
    "zhipu_llm",
    "deepseek_llm",
    "groq_llm",
    "mistral_llm",
    "lmstudio_llm",
}


class LLMFactory:
    @staticmethod
    def create_llm(llm_provider: str, **kwargs) -> Type[StatelessLLMInterface]:
        logger.info(f"Initializing LLM: {llm_provider}")

        if llm_provider in _OPENAI_COMPATIBLE_PROVIDERS:
            return OpenAICompatibleLLM(
                model=kwargs.get("model"),
                base_url=kwargs.get("base_url"),
                llm_api_key=kwargs.get("llm_api_key"),
                organization_id=kwargs.get("organization_id"),
                project_id=kwargs.get("project_id"),
                temperature=kwargs.get("temperature"),
            )

        raise ValueError(f"Unsupported LLM provider: {llm_provider}")
