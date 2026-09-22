# AI 求籤互動系統 API 文件

本文件以目前 Django/Channels 實作為準，涵蓋 REST API、語音轉寫、Live2D HTTP 資源與 WebSocket 協定。

## 連線資訊

| 項目 | 本機開發 | 說明 |
|---|---|---|
| REST Base URL | `http://localhost:8003/api/v1` | `DJANGO_RUNSERVER_DEFAULT_PORT` 可調整；Docker 通常使用 `8000` |
| WebSocket | `ws://localhost:8003/client-ws` | HTTPS 部署時使用 `wss://` |
| Django Admin | `http://localhost:8003/admin/` | 非 REST API |

瀏覽器前端通常使用相對路徑 `/api/v1` 與 `/client-ws`，由反向代理或 Vite proxy 轉發至後端。

JSON request 請帶：

```http
Content-Type: application/json
```

需要 JWT 的端點請帶：

```http
Authorization: Bearer <access_token>
```

## 通用回應格式

大部分自訂端點成功時回傳：

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

錯誤時回傳：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_SESSION_STATE",
    "message": "目前狀態不可抽籤",
    "details": { "detail": "目前狀態不可抽籤" }
  }
}
```

欄位驗證失敗時 `code` 通常為 `INVALID`，`details` 是欄位對應的錯誤陣列。JWT 的 token 取得與更新端點是 Simple JWT 原生格式，不使用上述 envelope。

### 常用錯誤碼

| code | HTTP | 說明 |
|---|---:|---|
| `INVALID` | 400 | 欄位缺漏、格式錯誤或選項不合法 |
| `NOT_AUTHENTICATED` | 401 | 未提供或無效 JWT |
| `PERMISSION_DENIED` | 403 | 權限不足或未登入存取受保護紀錄 |
| `NOT_FOUND` | 404 | 資源不存在或不可透露其存在 |
| `FORTUNE_SET_NOT_FOUND` | 404 | 籤系不存在、未啟用或不公開 |
| `FORTUNE_NOT_FOUND` | 404 | 籤號不存在或籤詩未啟用 |
| `FORTUNE_DATA_UNAVAILABLE` | 409 | 籤系沒有可抽取的啟用籤詩 |
| `INVALID_SESSION_STATE` | 409 | 目前流程狀態不允許此操作 |
| `INTERPRETATION_IN_PROGRESS` | 409 | 同一筆紀錄已有解籤請求處理中 |
| `CHAT_LIMIT_REACHED` | 409 | 已達 5 次使用者聊天訊息上限 |
| `AI_SERVICE_UNAVAILABLE` | 503 | LLM 逾時、連線失敗或回傳無效內容 |

## 1. 認證 API

### 註冊

```http
POST /auth/register/
```

不需認證。

Request：

```json
{
  "username": "jimmy",
  "email": "jimmy@example.com",
  "password": "A-strong-password-123"
}
```

`password` 至少 8 字元，並須通過 Django 密碼驗證規則；`username` 不可重複。

成功回傳 `201`：

```json
{
  "success": true,
  "data": {
    "user": { "id": 1, "username": "jimmy", "email": "jimmy@example.com" },
    "access": "<JWT access token>",
    "refresh": "<JWT refresh token>"
  },
  "message": "操作成功"
}
```

### 取得 JWT

```http
POST /auth/token/
```

不需認證。Simple JWT 原生回應，不含 `success`/`data`：

```json
{
  "username": "jimmy",
  "password": "A-strong-password-123"
}
```

```json
{
  "refresh": "<JWT refresh token>",
  "access": "<JWT access token>"
}
```

### 更新 access token

```http
POST /auth/token/refresh/
```

Request：`{ "refresh": "<JWT refresh token>" }`；成功回傳 `{ "access": "..." }`。

### 目前使用者

```http
GET /auth/me/
```

需要 JWT。`data` 為 `{ "id", "username", "email" }`。

## 2. 籤詩 API

### 列出公開籤系

```http
GET /fortune-sets/
```

不需認證。只回傳 `is_active=true` 且 `is_public=true` 的籤系，預設籤系優先，其餘依名稱排序。

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "code": "SIXTY_JIAZI",
        "name": "六十甲子籤",
        "description": "...",
        "is_default": true
      }
    ]
  },
  "message": "操作成功"
}
```

### 查詢籤詩

```http
GET /fortune-sets/{fortune_set_code}/fortunes/{number}/
```

不需認證。只可查詢公開且啟用籤系中的啟用籤詩。`number` 必須是正整數。

`data` 欄位：

```text
number, title, ganzhi, poem, translation, story,
general_meaning, love_meaning, career_meaning, study_meaning,
wealth_meaning, health_meaning, family_meaning, relationship_meaning,
travel_meaning
```

### 管理員批次匯入籤詩

```http
POST /admin/fortune-sets/{fortune_set_code}/fortunes/import/
```

需要 `is_staff=true` 的 JWT。整批資料在一個 transaction 中以 `number` 建立或更新；任一筆驗證失敗時全部回滾。

Request：

```json
{
  "items": [
    {
      "number": 1,
      "title": "第一籤",
      "poem": "籤詩內容",
      "translation": "白話解釋",
      "is_active": true
    }
  ]
}
```

`number`、`poem` 為必要欄位；其餘可使用籤詩詳情欄位，另可帶 `source_reference`、`is_active`。成功回傳：`{ "imported": 1 }`。

## 3. 求籤 API

### 可用值

`categories`：`love`、`career`、`study`、`wealth`、`health`、`family`、`relationship`、`travel`、`other`。

`interaction_mode`：`click`、`motion`。

### 建立求籤紀錄

```http
POST /divinations/
```

不需認證；帶有效 JWT 時，紀錄會綁定該使用者。

Request：

```json
{
  "fortune_set_code": "SIXTY_JIAZI",
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "interaction_mode": "click",
  "anonymous_user_id": "browser-unique-id",
  "fortune_number": 1
}
```

欄位規則：

- `fortune_set_code` 可省略，預設使用目前 `is_default=true` 且啟用的籤系；指定籤系必須公開且啟用。
- `question` 必填，2–300 字元。
- `categories` 必填且不可為空陣列；重複值會被去除。舊的單數欄位 `category` 不接受。
- `interaction_mode` 必填。
- `anonymous_user_id` 選填，最多 100 字元。
- `fortune_number` 選填且必須為正整數。提供時會查詢啟用籤詩，建立後直接為 `confirmed`，跳過祈求、抽籤與擲筊。

成功回傳 `201`，`data` 為求籤紀錄物件。

### 列出求籤紀錄

```http
GET /divinations/?anonymous_user_id={id}
```

- 已登入：只回傳目前使用者最近 50 筆，忽略 query parameter。
- 未登入：必須帶 `anonymous_user_id`；未帶時回傳空陣列。

### 求籤紀錄物件

```json
{
  "session_id": "6b3e1cd9-ba83-4da3-93cc-16a0aa4e7a4d",
  "share_token": "<UUID>",
  "user": null,
  "anonymous_user_id": "browser-unique-id",
  "fortune_set": { "code": "SIXTY_JIAZI", "name": "六十甲子籤", "description": "...", "is_default": true },
  "fortune": null,
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "interaction_mode": "click",
  "status": "created",
  "confirmed": false,
  "interpretation": null,
  "ai_interpretation": "",
  "created_at": "2026-07-14T00:00:00Z",
  "updated_at": "2026-07-14T00:00:00Z",
  "completed_at": null
}
```

`fortune` 有值時使用「查詢籤詩」的欄位格式。解籤完成後 `interpretation` 為：

```json
{
  "overall_meaning": "<Markdown 解籤全文>",
  "relation_to_question": "",
  "suggested_actions": [],
  "warnings": ["本系統僅供文化體驗及參考。"]
}
```

### 讀取一筆紀錄

```http
GET /divinations/{session_id}/
```

綁定使用者的紀錄只能由擁有者讀取；匿名紀錄可由持有 `session_id` 者讀取。也可使用分享 token：

```http
GET /divinations/{session_id}/?share={share_token}
```

有效的 `share_token` 可繞過擁有者檢查。

### 刪除一筆紀錄

```http
DELETE /divinations/{session_id}/
```

存取規則同讀取端點。成功回傳：

```json
{ "success": true, "data": {}, "message": "已刪除" }
```

### 完成祈求

```http
POST /divinations/{session_id}/prayer-complete/
```

無 request body。`created` 或 `praying` 狀態可呼叫，成功後狀態變為 `drawing`。

### 抽籤

```http
POST /divinations/{session_id}/draw/
```

無 request body。正常僅限 `drawing` 狀態，從所屬籤系的啟用籤詩隨機抽出一支並變為 `waiting_for_blocks`。若已有籤詩，重複呼叫會直接回傳原紀錄，不會重抽。

### 擲筊

```http
POST /divinations/{session_id}/blocks/
```

無 request body。僅限 `waiting_for_blocks` 狀態。成功後紀錄變為 `confirmed`，回應格式：

```json
{
  "success": true,
  "data": {
    "attempt_number": 1,
    "block_one": "flat",
    "block_two": "round",
    "result": "sheng",
    "result_name": "聖筊",
    "confirmed": true,
    "remaining_attempts": 0
  },
  "message": "操作成功"
}
```

目前實作讓兩個筊杯必定為一平一凸，因此 API 實際上會在第一次回傳 `sheng`；資料模型仍保留 `xiao`（笑筊）與 `yin`（陰筊）選項供後續流程使用。

### AI 解籤

```http
POST /divinations/{session_id}/interpret/
```

僅限 `confirmed=true` 且有籤詩的紀錄。Request body 可省略，也可帶：

```json
{
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "divination_result": {}
}
```

`question` 與 `categories` 若提供會覆寫該次解籤使用的資料；`divination_result` 僅為保留欄位，目前不參與提示詞。成功後狀態為 `completed`。已完成且已有結果時會直接回傳既有結果；AI 失敗時紀錄會保留並還原原狀態，可重試。

### 認領匿名紀錄

```http
POST /divinations/{session_id}/claim/
```

需要 JWT，無 request body。將匿名紀錄綁定到目前使用者並清空 `anonymous_user_id`。若本來就是目前使用者的紀錄，會直接回傳成功，方便安全重試；不存在、已屬於他人或已非匿名紀錄時，統一回傳 `404 NOT_FOUND`。

### AI 對話紀錄

#### 讀取對話

```http
GET /divinations/{session_id}/chat/
```

需要 JWT，且只能由紀錄擁有者讀取。必須已完成解籤，否則回傳 `409 INVALID_SESSION_STATE`。

```json
{
  "success": true,
  "data": {
    "messages": [
      { "id": 5, "role": "user", "content": "請再說明", "created_at": "2026-07-14T00:05:00Z" },
      { "id": 6, "role": "assistant", "content": "...", "created_at": "2026-07-14T00:05:03Z" }
    ],
    "remaining_messages": 4
  },
  "message": "操作成功"
}
```

初始解籤所建立的 system/user/assistant prompt 會標記為隱藏，不會出現在此列表。

#### 傳送聊天訊息

```http
POST /divinations/{session_id}/chat/
```

Request：

```json
{ "message": "請再說明我該注意的事項" }
```

`message` 長度為 1–250 字元；每筆求籤紀錄最多 5 次使用者聊天訊息。成功回傳 `reply`、完整可見 `messages` 與剩餘次數。匿名紀錄可用 `session_id`（或有效 `share` query）傳送訊息，但不能使用 GET 讀取歷史；已綁定紀錄則須由擁有者傳送。

### 建議流程

```text
POST 建立紀錄
→ POST prayer-complete
→ POST draw
→ POST blocks
→ POST interpret
→ POST chat（可選）
```

建立時帶 `fortune_number` 時，直接從 `confirmed` 開始，接著呼叫 `interpret`。

常見狀態值：`created`、`praying`、`drawing`、`waiting_for_blocks`、`confirmed`、`rejected`、`interpreting`、`completed`、`cancelled`。目前一般 API 流程實際會使用 `created`、`drawing`、`waiting_for_blocks`、`confirmed`、`interpreting`、`completed`。

## 4. 系統與語音 API

### 健康檢查

```http
GET /health/
```

不需認證。只確認 HTTP 服務存活，不檢查資料庫或外部 LLM；成功回傳 `data.status = "ok"`。

### 管理員使用統計

```http
GET /admin/usage-stats/
```

需要 `is_staff=true` 的 JWT。回傳：

```json
{
  "total_sessions": 100,
  "completed_sessions": 80,
  "by_status": [{ "status": "completed", "count": 80 }],
  "by_category": [{ "category": "career", "count": 20 }]
}
```

### 語音轉文字

```http
POST /speech/transcribe/
```

不需認證，使用 `multipart/form-data`，欄位名稱為 `audio`。檔案內容必須是 **16 kHz、單聲道、float32 little-endian 原始 PCM**；前端應使用副檔名 `.f32` 或 `application/octet-stream`。

限制：最短 0.3 秒、最長 60 秒（單檔最多 `3,840,000` bytes）。

成功回傳：

```json
{
  "success": true,
  "data": {
    "text": "辨識結果",
    "engine": "cloud",
    "language": "zh",
    "duration": 2.34
  },
  "message": "操作成功"
}
```

錯誤碼：`AUDIO_REQUIRED`（400）、`AUDIO_MALFORMED`（400）、`AUDIO_TOO_SHORT`（400）、`AUDIO_SILENT`（400）、`AUDIO_TOO_LONG`（413）、`ASR_UNAVAILABLE`（503）、`ASR_FAILED`（500）。

## 5. Live2D HTTP 資源

這些路徑位於 REST base path 之外：

| Method | Path | 說明 |
|---|---|---|
| GET | `/live2d-models/info` | 回傳可用角色模型資訊 |
| GET | `/live2d-models/{path}` | Live2D 模型檔案 |
| GET | `/avatars/{path}` | 角色頭像 |
| GET | `/bg/{path}` | 背景圖片 |
| GET | `/cache/{path}` | TTS 快取檔案 |

`GET /live2d-models/info` 成功回傳：

```json
{
  "type": "live2d-models/info",
  "count": 1,
  "characters": [
    {
      "name": "mao_pro",
      "avatar": null,
      "model_path": "/live2d-models/mao_pro/runtime/mao_pro.model3.json",
      "model_info": {
        "name": "mao_pro",
        "description": "...",
        "url": "/live2d-models/mao_pro/runtime/mao_pro.model3.json",
        "kScale": 0.5,
        "initialXshift": 0,
        "initialYshift": 0,
        "idleMotionGroupName": "Idle",
        "emotionMap": {}
      }
    }
  ]
}
```

模型目錄不存在時回傳 `404`。

## 6. Live2D WebSocket

### 連線

```text
ws://<host>/client-ws
```

目前不使用 JWT。每條連線有獨立角色記憶與對話歷史；伺服器在連線建立後會送出 `full-text` 與 `set-model-and-conf`。

所有訊息都是 JSON text frame，至少包含 `type`。

### Client → Server

| type | payload | 說明 |
|---|---|---|
| `text-input` | `{ "text": "..." }` | 送出文字並觸發角色回覆 |
| `mic-audio-data` | `{ "audio": [0.1, -0.1] }` | 追加 float32 音訊樣本 |
| `mic-audio-end` | 無 | 結束音訊並觸發 ASR/回覆 |
| `speak-text` | `{ "text": "..." }` | 直接 TTS，不經 LLM |
| `remember-context` | `{ "text": "..." }` | 靜默寫入角色記憶 |
| `interrupt-signal` | `{ "text": "..." }` | 中斷目前回覆並保存已播放文字 |
| `fetch-history-list` | 無 | 取得歷史列表 |
| `fetch-and-set-history` | `{ "history_uid": "..." }` | 載入指定歷史 |
| `create-new-history` | 無 | 建立新歷史 |
| `delete-history` | `{ "history_uid": "..." }` | 刪除歷史 |
| `fetch-configs` | 無 | 取得角色設定列表 |
| `fetch-backgrounds` | 無 | 取得背景列表 |
| `request-init-config` | 無 | 要求重新送出模型設定 |
| `heartbeat` | 無 | 心跳 |
| `frontend-playback-complete` | 無 | 告知前端已播放完 TTS |

### Server → Client

| type | 主要欄位 | 說明 |
|---|---|---|
| `full-text` | `text` | 連線訊息或目前狀態文字 |
| `set-model-and-conf` | `model_info`, `conf_name`, `conf_uid`, `client_uid` | 角色模型與設定 |
| `control` | `text` | `conversation-chain-start` 或 `conversation-chain-end` |
| `audio` | `audio`, `volumes`, `slice_length`, `display_text`, `actions` | TTS 音訊；`audio` 是 Base64 WAV |
| `user-input-transcription` | `text` | WebSocket 麥克風輸入的 ASR 結果 |
| `backend-synth-complete` | 無 | 後端 TTS 產生完成 |
| `force-new-message` | 無 | 要求前端開始新的訊息區段 |
| `history-list` | `histories` | 歷史列表 |
| `history-data` | `messages` | 指定歷史內容 |
| `new-history-created` | `history_uid` | 新歷史 ID |
| `history-deleted` | `success`, `history_uid` | 刪除結果 |
| `config-files` | `configs` | 設定檔列表 |
| `background-files` | `files` | 背景檔名列表 |
| `heartbeat-ack` | 無 | 心跳回覆 |
| `error` | `message` | 處理錯誤 |

`audio` 訊息範例：

```json
{
  "type": "audio",
  "audio": "<base64 WAV>",
  "volumes": [0.12, 0.34, 0.2],
  "slice_length": 20,
  "display_text": { "text": "你好", "name": "金鶴", "avatar": null },
  "actions": { "expressions": ["smile"] }
}
```

## 7. 非 API 管理介面

`/admin/` 是 Django Admin，用於管理資料庫，不使用 REST envelope，也不屬於本文件的 REST API。
