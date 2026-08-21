"""Per-session bundle of the LLM/ASR/TTS engines, Live2D model info, and system prompt.

Trimmed from upstream open_llm_vtuber's ServiceContext: MCP tool-calling, VAD, translation,
and runtime character-switching (`handle_config_switch`) are dropped — this deployment
serves a single fixed character and the current live2d-frontend (pet mode) never sends a
config-switch message anyway.

Bug fixed while porting: upstream shares one `agent_engine` instance (and therefore one
conversation memory) across every client that hasn't switched character config, since
`load_cache()` copies it by reference like the (genuinely stateless, safe-to-share) ASR/TTS
engines. Here, only `live2d_model`/`asr_engine`/`tts_engine` are shared by reference from the
startup-time default context; each session builds its OWN `agent_engine` via `init_agent()`,
so concurrent conversations never bleed into each other's memory.
"""

from loguru import logger

from .agent.agent_factory import AgentFactory
from .agent.agents.agent_interface import AgentInterface
from .asr.asr_factory import ASRFactory
from .asr.asr_interface import ASRInterface
from .config_manager import AgentConfig, ASRConfig, CharacterConfig, Config, SystemConfig, TTSConfig
from .live2d_model import Live2dModel
from .tts.tts_factory import TTSFactory
from .tts.tts_interface import TTSInterface

_LIVE2D_EXPRESSION_PROMPT_TEMPLATE = """## Expressions
In your response, use the keywords provided below to express facial expressions or perform actions with your Live2D body.

Here are all the expression keywords you can use. Use them regularly:
- [<insert_emomap_keys>]

## Examples
Here are some examples of how to use expressions in your responses:

"Hi! [expression1] Nice to meet you!"

"[expression2] That's a great question! [expression3] Let me explain..."

Note: you are only allowed to use the keywords explicity listed above. Don't use keywords unlisted above. Remember to include the brackets `[]`"""


class ServiceContext:
    """Holds the ASR/TTS/agent engines and config for one connected client."""

    def __init__(self):
        self.config: Config | None = None
        self.system_config: SystemConfig | None = None
        self.character_config: CharacterConfig | None = None

        self.live2d_model: Live2dModel | None = None
        self.asr_engine: ASRInterface | None = None
        self.tts_engine: TTSInterface | None = None
        self.agent_engine: AgentInterface | None = None

        self.system_prompt: str | None = None
        self.history_uid: str = ""
        self.client_uid: str | None = None

    def __str__(self):
        return (
            f"ServiceContext(client_uid={self.client_uid}, "
            f"asr={type(self.asr_engine).__name__ if self.asr_engine else None}, "
            f"tts={type(self.tts_engine).__name__ if self.tts_engine else None}, "
            f"agent={type(self.agent_engine).__name__ if self.agent_engine else None})"
        )

    async def close(self):
        pass

    async def load_cache(
        self,
        config: Config,
        system_config: SystemConfig,
        character_config: CharacterConfig,
        live2d_model: Live2dModel,
        asr_engine: ASRInterface,
        tts_engine: TTSInterface,
        client_uid: str | None = None,
    ) -> None:
        """Adopt the shared, stateless engines by reference; build a fresh, independent
        agent_engine for this session (see module docstring for why)."""
        if not character_config:
            raise ValueError("character_config cannot be None")
        if not system_config:
            raise ValueError("system_config cannot be None")

        self.config = config
        self.system_config = system_config
        self.character_config = character_config.model_copy(deep=True)
        self.live2d_model = live2d_model
        self.asr_engine = asr_engine
        self.tts_engine = tts_engine
        self.client_uid = client_uid

        await self.init_agent(self.character_config.agent_config, self.character_config.persona_prompt)
        logger.debug(f"Loaded service context for client {client_uid}")

    async def load_from_config(self, config: Config) -> None:
        """Build the startup-time default context: loads real ASR/TTS/agent engines."""
        self.config = config
        self.system_config = config.system_config
        self.character_config = config.character_config

        self.init_live2d(config.character_config.live2d_model_name)
        self.init_asr(config.character_config.asr_config)
        self.init_tts(config.character_config.tts_config)
        await self.init_agent(config.character_config.agent_config, config.character_config.persona_prompt)

    def init_live2d(self, live2d_model_name: str) -> None:
        logger.info(f"Initializing Live2D: {live2d_model_name}")
        try:
            self.live2d_model = Live2dModel(live2d_model_name, model_dict_path=str(_model_dict_path()))
            self.character_config.live2d_model_name = live2d_model_name
        except Exception as e:
            logger.critical(f"Error initializing Live2D: {e}")

    def init_asr(self, asr_config: ASRConfig) -> None:
        if not self.asr_engine or self.character_config.asr_config != asr_config:
            logger.info(f"Initializing ASR: {asr_config.asr_model}")
            try:
                self.asr_engine = ASRFactory.get_asr_system(
                    asr_config.asr_model,
                    **getattr(asr_config, asr_config.asr_model).model_dump(),
                )
                self.character_config.asr_config = asr_config
            except Exception as e:
                # 跟 init_live2d 一樣優雅降級:語音模型缺失/載入失敗時只關掉語音
                # 輸入,不能讓整條 WebSocket 連線炸掉、連累角色渲染跟文字聊天。
                logger.critical(f"Error initializing ASR: {e}")
                self.asr_engine = None

    def init_tts(self, tts_config: TTSConfig) -> None:
        if not self.tts_engine or self.character_config.tts_config != tts_config:
            logger.info(f"Initializing TTS: {tts_config.tts_model}")
            self.tts_engine = TTSFactory.get_tts_engine(
                tts_config.tts_model,
                **getattr(tts_config, tts_config.tts_model.lower()).model_dump(),
            )
            self.character_config.tts_config = tts_config

    async def init_agent(self, agent_config: AgentConfig, persona_prompt: str) -> None:
        logger.info(f"Initializing Agent: {agent_config.conversation_agent_choice}")
        system_prompt = self.construct_system_prompt(persona_prompt)

        self.agent_engine = AgentFactory.create_agent(
            conversation_agent_choice=agent_config.conversation_agent_choice,
            agent_settings=agent_config.agent_settings.model_dump(),
            llm_configs=agent_config.llm_configs.model_dump(),
            system_prompt=system_prompt,
            live2d_model=self.live2d_model,
            tts_preprocessor_config=self.character_config.tts_preprocessor_config,
        )
        self.character_config.agent_config = agent_config
        self.system_prompt = system_prompt

    def construct_system_prompt(self, persona_prompt: str) -> str:
        persona_prompt += "\n請一律使用繁體中文回覆。\n"
        persona_prompt += (
            "請遵守既有角色設定及所有指定的輸出格式。"
            "資訊不足時請明確說明不確定性，不要捏造；"
            "避免無意義的連續重複，並依目前設定的回覆長度上限保持精簡。\n"
        )
        persona_prompt += _LIVE2D_EXPRESSION_PROMPT_TEMPLATE.replace(
            "[<insert_emomap_keys>]", self.live2d_model.emo_str
        )
        logger.debug(f"System prompt: {persona_prompt}")
        return persona_prompt

    def update_max_response_characters(self, value: int) -> None:
        if not 1 <= value <= 10_000:
            raise ValueError("max_response_characters must be between 1 and 10000")
        update_limit = getattr(self.agent_engine, "set_max_response_characters", None)
        if update_limit is None:
            raise ValueError("The active agent does not support response length limits")
        update_limit(value)


def _model_dict_path():
    from .paths import DATA_DIR

    return DATA_DIR / "model_dict.json"
