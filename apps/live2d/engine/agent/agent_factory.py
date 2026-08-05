from typing import Type

from loguru import logger

from .agents.agent_interface import AgentInterface
from .agents.basic_memory_agent import BasicMemoryAgent
from .stateless_llm_factory import LLMFactory as StatelessLLMFactory


class AgentFactory:
    @staticmethod
    def create_agent(
        conversation_agent_choice: str,
        agent_settings: dict,
        llm_configs: dict,
        system_prompt: str,
        live2d_model=None,
        tts_preprocessor_config=None,
        **kwargs,
    ) -> Type[AgentInterface]:
        logger.info(f"Initializing agent: {conversation_agent_choice}")

        if conversation_agent_choice != "basic_memory_agent":
            raise ValueError(f"Unsupported agent type: {conversation_agent_choice}")

        basic_memory_settings: dict = agent_settings.get("basic_memory_agent", {})
        llm_provider: str = basic_memory_settings.get("llm_provider")
        if not llm_provider:
            raise ValueError("LLM provider not specified for basic memory agent")

        llm_config: dict = dict(llm_configs.get(llm_provider) or {})
        if not llm_config:
            raise ValueError(f"Configuration not found for LLM provider: {llm_provider}")
        interrupt_method = llm_config.pop("interrupt_method", "user")

        llm = StatelessLLMFactory.create_llm(llm_provider=llm_provider, system_prompt=system_prompt, **llm_config)

        return BasicMemoryAgent(
            llm=llm,
            system=system_prompt,
            live2d_model=live2d_model,
            tts_preprocessor_config=tts_preprocessor_config,
            faster_first_response=basic_memory_settings.get("faster_first_response", True),
            segment_method=basic_memory_settings.get("segment_method", "pysbd"),
            interrupt_method=interrupt_method,
            max_response_characters=basic_memory_settings.get("max_response_characters", 500),
        )
