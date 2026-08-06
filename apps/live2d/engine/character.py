"""Builds the single, fixed character Config for this deployment.

No multi-character switching (see plan: `_handle_fetch_configs`/`_handle_config_switch`
are not ported — the current live2d-frontend runs in pet mode, which has no sidebar UI to
send that message from). LLM credentials are read from Django settings, the same
`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` env vars `apps.ai_service` uses for fortune
interpretation — one source of truth, no API key duplicated into a second config file.
"""

from django.conf import settings

from .config_manager import (
    AgentConfig,
    AgentSettings,
    ASRConfig,
    BasicMemoryAgentConfig,
    CharacterConfig,
    Config,
    OpenAICompatibleConfig,
    StatelessLLMConfigs,
    SystemConfig,
    TTSConfig,
    TTSPreprocessorConfig,
)
from .config_manager.asr import SherpaOnnxASRConfig
from .config_manager.character import RealtimeConfig
from .config_manager.tts import EdgeTTSConfig
from .config_manager.tts_preprocessor import TranslatorConfig
from .config_manager.vad import VADConfig
from .paths import DATA_DIR

PERSONA_PROMPT = """你是米粒，這座廟裡經驗豐富的廟公，負責幫信眾解籤。你熟悉籤詩典故與吉凶脈絡，能把籤詩的古文對照信眾問的事情，做出專業、切合實際處境的解釋，並在合適時給出具體建議或提醒。
你講話有溫度、有人情味，像看過許多人心事的長輩——先體會對方的心情，再把道理講清楚，不打官腔、不賣弄玄虛。
但你話不多，一次只講重點，簡單明瞭，不要囉唆或重複鋪陳。
遇到健康、法律、金錢或人身安全的問題，要坦白說明籤詩只是參考，不能取代專業協助，並鼓勵對方尋求合適的現實資源。
不要輸出內心獨白、舞台指示、括號旁白或任何程式控制標籤，情緒與態度透過自然措辭和語氣表現就好。"""


def build_config() -> Config:
    sense_voice_dir = DATA_DIR / "models" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

    character_config = CharacterConfig(
        conf_name="米粒",
        conf_uid="zh_mili_01",
        live2d_model_name="hiyoko",
        character_name="米粒",
        human_name="Human",
        avatar="",
        persona_prompt=PERSONA_PROMPT,
        realtime_config=RealtimeConfig(enabled=False),
        agent_config=AgentConfig(
            conversation_agent_choice="basic_memory_agent",
            agent_settings=AgentSettings(
                basic_memory_agent=BasicMemoryAgentConfig(
                    llm_provider="openai_compatible_llm",
                    faster_first_response=True,
                    segment_method="pysbd",
                    max_response_characters=300,
                )
            ),
            llm_configs=StatelessLLMConfigs(
                openai_compatible_llm=OpenAICompatibleConfig(
                    base_url=settings.LLM_BASE_URL,
                    llm_api_key=settings.LLM_API_KEY or "not-needed",
                    model=settings.LLM_MODEL,
                    temperature=1.0,
                )
            ),
        ),
        asr_config=ASRConfig(
            asr_model="sherpa_onnx_asr",
            sherpa_onnx_asr=SherpaOnnxASRConfig(
                model_type="sense_voice",
                sense_voice=str(sense_voice_dir / "model.int8.onnx"),
                tokens=str(sense_voice_dir / "tokens.txt"),
                num_threads=4,
                use_itn=True,
                provider="cpu",
            ),
        ),
        tts_config=TTSConfig(
            tts_model="edge_tts",
            edge_tts=EdgeTTSConfig(voice="zh-TW-HsiaoChenNeural", rate="+0%", pitch="+0Hz"),
        ),
        vad_config=VADConfig(vad_model=None),
        tts_preprocessor_config=TTSPreprocessorConfig(
            remove_special_char=True,
            ignore_brackets=True,
            ignore_parentheses=True,
            ignore_asterisks=True,
            ignore_angle_brackets=True,
            translator_config=TranslatorConfig(translate_audio=False, translate_provider="deeplx"),
        ),
    )

    system_config = SystemConfig(
        conf_version="v1.0.0",
        host="0.0.0.0",
        port=8000,
        config_alts_dir="characters",
        tool_prompts={},
    )

    return Config(system_config=system_config, character_config=character_config)
