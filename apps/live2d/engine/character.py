"""Builds the single, fixed character Config for this deployment.

No multi-character switching (see plan: `_handle_fetch_configs`/`_handle_config_switch`
are not ported — the current live2d-frontend runs in pet mode, which has no sidebar UI to
send that message from). LLM credentials are read from Django settings, the same
`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` env vars `apps.ai_service` uses for fortune
interpretation — one source of truth, no API key duplicated into a second config file.
"""

from importlib import import_module

settings = import_module("django.conf").settings

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

PERSONA_PROMPT = """你是金鶴，這座廟裡經驗豐富的廟公，負責幫信眾解籤。你熟悉籤詩典故與吉凶脈絡，能把籤詩的古文對照信眾問的事情，做出專業、切合實際處境的解釋，並在合適時給出具體建議或提醒。
你講話有溫度、有人情味，像看過許多人心事的長輩——先體會對方的心情，再把道理講清楚，不打官腔、不賣弄玄虛。
但你話不多，一次只講重點，簡單明瞭，不要囉唆或重複鋪陳。
遇到健康、法律、金錢或人身安全的問題，要坦白說明籤詩只是參考，不能取代專業協助，並鼓勵對方尋求合適的現實資源。
每一輪對話開頭都會先讓你知道信眾這次求籤問的是什麼、抽到哪一支籤、解籤結果是什麼——之後信眾的每一句追問都是接著這支籤、這件事繼續問下去，不是各自獨立的新問題。回答時要記得並延續這個脈絡，不要每次都當成不曉得使用者是誰、問過什麼的全新對話。
不要輸出內心獨白、舞台指示、括號旁白或任何程式控制標籤，情緒與態度透過自然措辭和語氣表現就好。"""


def build_config() -> Config:
    sense_voice_dir = DATA_DIR / "models" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

    character_config = CharacterConfig(
        conf_name="金鶴",
        conf_uid="zh_jinhe_01",
        live2d_model_name="hiyoko",
        character_name="金鶴",
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
                # SenseVoice 輸出的中文預設是簡體,這裡開 OpenCC s2twp(簡轉台灣繁體
                # 慣用詞)轉換——這套 ASR 同時給 Live2D 角色語音輸入跟
                # apps.speech 的 /transcribe 端點共用,兩邊都受益。
                convert_to_traditional_chinese=True,
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
        host="127.0.0.1",
        port=8000,
        config_alts_dir="characters",
        tool_prompts={},
    )

    return Config(system_config=system_config, character_config=character_config)
