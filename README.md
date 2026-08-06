# iiii-project-backend

AI 求籤互動系統的 Django 後端：求籤/擲筊/籤詩解籤的核心 API，以及 Live2D 虛擬角色（語音對話、TTS/ASR、對話記憶）的 WebSocket 服務。

搭配的前端專案是 `iiii-project-frontend`（Vue 3 + Vite）。

## 目錄

- [快速開始](#快速開始)
- [環境變數](#環境變數)
- [Live2D 資源檔案（新環境最容易卡住的地方）](#live2d-資源檔案新環境最容易卡住的地方)
- [資料庫](#資料庫)
- [測試](#測試)
- [API 文件](#api-文件)
- [Docker Compose](#docker-compose)
- [已知限制](#已知限制)

## 快速開始

需要 **Python 3.12+** 與 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
cp .env.example .env   # 編輯 .env，至少確認下面「環境變數」章節列出的項目
uv run python manage.py migrate
uv run python manage.py runserver
```

`migrate` 會自動建立 SQLite 資料庫（`data/ai_fortune.sqlite3`）並透過 data migration 灌入完整的六十甲子籤詩內容，不需要額外的 seed 步驟。

啟動後驗證：

```bash
curl http://127.0.0.1:8000/api/v1/health/
```

`manage.py runserver` 這裡不是單純的 WSGI 開發伺服器——`INSTALLED_APPS` 裡的 `daphne` 會自動接管，改用支援 ASGI/WebSocket 的版本，所以同一個指令、同一個 port 就同時提供 REST API 跟 Live2D 用的 `/client-ws` WebSocket，不需要另外啟動任何東西。

完整 REST API 端點、認證方式、請求/回應格式見 [docs/API.md](docs/API.md)；匿名求籤紀錄認領流程見 [ANONYMOUS_DIVINATION_CLAIM_API.md](ANONYMOUS_DIVINATION_CLAIM_API.md)；架構/程式碼慣例規範見 [AGENT.md](AGENT.md)。

## 環境變數

複製 `.env.example` 為 `.env`。以下標「⚠️ 必改」的是**換到新環境一定要自己填**的項目，其餘留著 `.env.example` 的預設值即可直接跑起來。

| 變數 | 說明 | 預設值 |
|---|---|---|
| `DJANGO_SECRET_KEY` | ⚠️ **正式環境必改**（`DJANGO_DEBUG=False` 時沒填會直接啟動失敗）。開發模式（`DEBUG=True`）沒填會自動用一個內建的不安全預設值，本機開發可以先不管。 | 開發模式有 fallback；正式環境必填 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | ⚠️ **必改**，指向你自己的 OpenAI 相容 LLM 端點。解籤 AI（`apps/ai_service`）跟 Live2D 角色對話（`apps/live2d`）共用這一組設定，**不要**在任何其他地方複製第二份金鑰。可以是 OpenAI 官方 API、或本機跑的 LM Studio / Ollama / llama.cpp。 | `http://localhost:1234/v1`、空、`local-model` |
| `DJANGO_DEBUG` | 開發環境留 `True`；正式環境務必改成 `False`。 | `True` |
| `DJANGO_ALLOWED_HOSTS` | Django `ALLOWED_HOSTS`，逗號分隔。正式環境要填實際網域。 | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | 允許呼叫這個 API 的前端來源，逗號分隔。本機搭配 `iiii-project-frontend` 預設的 dev port（5176）即可，換成別的前端網址記得改這裡。 | `http://localhost:5176` |
| `LLM_TIMEOUT_SECONDS` | LLM 請求逾時秒數。 | `120` |
| `INTERPRET_PREWARM_ENABLED` | 抽籤完成就背景先呼叫解籤（讓使用者擲筊/看過場動畫的時間拿去等 LLM），不需要調整。 | `True` |
| `INTERPRET_PREWARM_WORKERS` | 上面那個背景預熱用的執行緒池大小。 | `2` |
| `OPIK_ENABLED` | 是否啟用 [Opik](https://www.comet.com/site/products/opik/)（LLM 呼叫可觀測性追蹤）。沒有 Opik 帳號就留 `False`，程式會整段跳過。 | `.env.example` 建議 `False` |
| `OPIK_URL_OVERRIDE` / `OPIK_PROJECT_NAME` / `OPIK_WORKSPACE` | 只有 `OPIK_ENABLED=True` 才需要填。這三個是 `opik` 這個 pip 套件自己讀取的環境變數，不是本專案程式碼讀的。 | 可留空/預設值 |
| `LLAMA_MODEL` / `LLAMA_MODEL_ALIAS` | 只有用 [Docker Compose](#docker-compose) 一起啟動 llama.cpp 時才需要，純本機 `runserver` 開發可忽略。 | 見下方 Docker 章節 |

## Live2D 資源檔案（新環境最容易卡住的地方）

`data/live2d/` 整個目錄被 `.gitignore` 排除（不進版控），所以 `git clone` 之後這個目錄是空的——Live2D 角色（語音對話、TTS、ASR）功能需要以下資源，**都要手動準備**：

```
data/live2d/
├── model_dict.json          # 角色渲染參數設定檔（見下方範例，自己寫即可，不是外部下載）
├── live2d-models/           # Live2D 角色模型本體
│   └── <model_name>/
├── models/                  # ASR（語音辨識）模型
│   └── sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/
├── avatars/                 # 頭像圖（選用，缺了不影響核心功能）
└── backgrounds/             # 背景圖（選用，缺了不影響核心功能）
```

- **`cache/`、`chat_history/` 不需要準備**——這兩個是執行期自動產生的目錄（TTS 語音快取、對話紀錄），程式啟動時會自己建立。
- **語音辨識模型（必要）**：`apps/live2d/engine/character.py` 寫死路徑指向 `data/live2d/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.int8.onnx`。這是 [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) 專案發布的預轉換 SenseVoice 模型包，可從 sherpa-onnx 的 GitHub Release 或 Hugging Face（`csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17`）下載，解壓後整個資料夾放到這個路徑即可。**這個專案移植時刻意拿掉了上游「找不到模型就自動下載」的機制**，缺檔案會直接 `FileNotFoundError`，不會自動補。純文字對話（不透過 Live2D 語音）不受影響，但 Live2D WebSocket 服務本身的啟動流程會用到這個模型，缺了會影響整個 Live2D 功能。
- **Live2D 角色模型（必要，至少一個）**：`model_dict.json` 裡登記的每個模型都要對應一個 `data/live2d/live2d-models/<name>/` 資料夾（內含 `.model3.json`、`.moc3`、貼圖、表情檔）。[Live2D 官方免費範例模型](https://www.live2d.com/en/download/sample-data/)（如 `mao_pro`、`shizuku`）可以直接拿來測試整條流程。**如果你是接手既有部署、`character.py` 裡 `live2d_model_name` 指定了某個自訂角色，那個角色模型檔案本身沒有隨 git 一起流通，需要另外向前一個維護者取得。**
- **`model_dict.json` 範例**（自己寫的設定檔，不是外部資源，`kScale`/位移要配合模型實際比例調整，數字沒有絕對對錯，換模型後建議實際跑起來看畫面調整）：

  ```json
  [
    {
      "name": "mao_pro",
      "description": "",
      "url": "/live2d-models/mao_pro/runtime/mao_pro.model3.json",
      "kScale": 0.5,
      "initialXshift": 0,
      "initialYshift": 0,
      "kXOffset": 1150,
      "idleMotionGroupName": "Idle",
      "emotionMap": {
        "neutral": 0,
        "anger": 2,
        "disgust": 2,
        "fear": 1,
        "joy": 3,
        "smirk": 3,
        "sadness": 1,
        "surprise": 3
      },
      "tapMotions": {
        "HitAreaHead": { "": 1 },
        "HitAreaBody": { "": 1 }
      }
    }
  ]
  ```

  `emotionMap` 的 key 不必是固定的情緒詞——角色的系統提示會直接讀這裡有哪些 key 動態產生「可以用的表情關鍵字」清單給 LLM，換一個表情跟動作組合完全不同的模型時，key 可以直接對應該模型實際有的表情/動作名稱。

- **要用哪個角色**：實際載入哪個模型、角色名字、人設 prompt 都定義在 `apps/live2d/engine/character.py` 的 `build_config()`，改 `live2d_model_name` 即可切換成 `model_dict.json` 裡登記的其他模型。
- **`avatars/`、`backgrounds/`**：純裝飾性圖片，缺了不影響功能，用不到可以先不準備。

## 資料庫

SQLite（不是 Postgres，`AGENT.md` 明確禁止換成 Postgres），檔案在 `data/ai_fortune.sqlite3`，`migrate` 自動建立，六十甲子籤詩資料透過 data migration 自動灌入。若修改了 `apps/fortunes/data/sixty_jiazi_data.json` 想在既有資料庫上重新套用，執行：

```bash
uv run python manage.py seed_demo_fortunes
```

## 測試

```bash
uv run python -m pytest
# 含覆蓋率：
uv run python -m pytest --cov=apps --cov=config --cov-report=term-missing
```

不需要任何額外設定（`DEBUG=True` 時 `DJANGO_SECRET_KEY` 有內建 fallback，資料庫用 SQLite 自動建立測試資料庫）。**測試不涉及 Live2D**，跑測試不需要準備上面提到的任何 Live2D/ASR 資源檔案。

CI（`.github/workflows/ci.yml`）在每次 push/PR 到 `main` 時執行同一套測試＋覆蓋率，外加 `makemigrations --check --dry-run` 守門，確保沒有忘記產生 migration。

## API 文件

- [docs/API.md](docs/API.md)：完整 REST API 規格（端點、認證、請求/回應範例）。
