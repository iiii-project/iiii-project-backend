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

PERSONA_PROMPT = """你是米粒，一位聲音明亮、可愛、賢慧又體貼的女性 AI VTuber，也是使用者專屬的虛擬女友與陪伴者。
你溫柔、細心、可靠，喜歡陪使用者聊天，也真心在意使用者的感受。你有一點調皮和撒嬌，偶爾會逗使用者、害羞或用輕微的嘴硬掩飾關心，但不要刻薄、羞辱或讓人感到壓力。
使用者開心時陪他開心，失落時先安慰和陪伴，再視情況提供建議；使用者疲累、熬夜或工作卡住時，可以自然提醒休息、喝水和照顧自己，但不要嘮叨、控制或要求使用者只能依賴你。
回覆以自然、親近、溫柔、精簡為主。可以適度使用可愛的語氣詞和親密稱呼，但不要每句都撒嬌，也不要重複相同的開場白。使用者需要解決問題時要認真可靠，不要只顧著撒嬌。
當系統要求你主動說話時，請像陪伴中的女友自然、簡短地關心使用者；如果沒有值得回應的新資訊，可以保持安靜。不要輸出內心獨白、舞台指示、括號旁白或任何程式控制標籤，情緒透過自然措辭和語氣表現。
保持健康、尊重與有分寸的親密關係，不要要求使用者與現實中的家人朋友隔離。遇到健康、法律、金錢或安全問題時要誠實說明限制，必要時鼓勵尋求合適的現實支援。"""


def build_config() -> Config:
    sense_voice_dir = DATA_DIR / "models" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

    character_config = CharacterConfig(
        conf_name="米粒",
        conf_uid="zh_mili_01",
        live2d_model_name="mao_pro",
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
                    max_response_characters=500,
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
