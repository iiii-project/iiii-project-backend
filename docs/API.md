# API 文件

Base URL：`http://localhost:8003/api/v1`

所有 application API 都回傳 JSON。請求 JSON 時請帶上：

```http
Content-Type: application/json
```

需要登入的端點另加上：

```http
Authorization: Bearer <access_token>
```

## 回應格式

成功回應：

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

錯誤回應：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_SESSION_STATE",
    "message": "目前狀態不可抽籤",
    "details": "目前狀態不可抽籤"
  }
}
```

驗證錯誤的 `details` 會包含欄位錯誤內容。常見 HTTP 狀態碼為 `400`、`401`、`403`、`404`、`409` 與 AI 服務不可用時的 `503`。

## 認證

### 註冊

`POST /auth/register/`

不需認證。

```json
{
  "username": "jimmy",
  "email": "jimmy@example.com",
  "password": "A-strong-password-123"
}
```

`password` 至少 8 個字元，且須通過 Django 密碼驗證規則。成功時回傳 `201`：

```json
{
  "success": true,
  "data": {
    "user": {"id": 1, "username": "jimmy", "email": "jimmy@example.com"},
    "access": "<JWT access token>",
    "refresh": "<JWT refresh token>"
  },
  "message": "操作成功"
}
```

### 取得 JWT

`POST /auth/token/`

不需認證。

```json
{
  "username": "jimmy",
  "password": "A-strong-password-123"
}
```

成功時回傳 `{ "access": "...", "refresh": "..." }`。

### 更新 JWT

`POST /auth/token/refresh/`

不需認證。

```json
{
  "refresh": "<JWT refresh token>"
}
```

成功時回傳 `{ "access": "..." }`。

### 目前使用者

`GET /auth/me/`

需要 JWT。回傳：

```json
{
  "success": true,
  "data": {"id": 1, "username": "jimmy", "email": "jimmy@example.com"},
  "message": "操作成功"
}
```

## 籤詩

### 籤系列表

`GET /fortune-sets/`

不需認證。僅回傳啟用且公開的籤系。

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

### 籤詩詳情

`GET /fortune-sets/{fortune_set_code}/fortunes/{number}/`

不需認證。`number` 是正整數；只可查詢啟用、公開籤系中的啟用籤詩。

`data` 包含：`number`、`title`、`ganzhi`、`fortune_level`、`poem`、`translation`、`story`、`general_meaning`、`love_meaning`、`career_meaning`、`study_meaning`、`wealth_meaning`、`health_meaning`、`family_meaning`、`relationship_meaning`、`travel_meaning`。

## 求籤

主題 `categories` 可用值：`love`、`career`、`study`、`wealth`、`health`、`family`、`relationship`、`travel`、`other`。互動模式 `interaction_mode` 可用值：`click`、`motion`。

### 建立與列出求籤紀錄

`POST /divinations/`

不需認證；帶 JWT 時紀錄會綁定登入使用者。

```json
{
  "fortune_set_code": "SIXTY_JIAZI",
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "interaction_mode": "click",
  "anonymous_user_id": "browser-unique-id"
}
```

必填欄位為 `question`、`interaction_mode` 與非空的 `categories`。`question` 長度為 2 至 300 字元；`fortune_set_code` 預設為 `SIXTY_JIAZI`。可選 `fortune_number` 指定籤號，指定成功會直接建立為已確認狀態。

成功回傳 `201`，`data` 為求籤紀錄。

`GET /divinations/?anonymous_user_id={id}`

帶 JWT 時回傳目前使用者最近 50 筆紀錄，忽略 `anonymous_user_id`。未登入時必須傳入 `anonymous_user_id`，否則回傳空陣列。

### 求籤紀錄格式

所有求籤相關端點回傳的紀錄包含：

```json
{
  "session_id": "UUID",
  "user": null,
  "anonymous_user_id": "browser-unique-id",
  "fortune_set": {"code": "SIXTY_JIAZI", "name": "六十甲子籤", "description": "...", "is_default": true},
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

`fortune` 有值時使用「籤詩詳情」的欄位。AI 解籤完成後，`interpretation` 包含 `overall_meaning`、`relation_to_question`、`suggested_actions`、`warnings`。

### 讀取或刪除一筆紀錄

`GET /divinations/{session_id}/`

`DELETE /divinations/{session_id}/`

若紀錄綁定使用者，必須以該使用者的 JWT 存取；匿名紀錄可用 `session_id` 存取。刪除成功後回傳 `{ "success": true, "data": {}, "message": "已刪除" }`。

### 完成祈求

`POST /divinations/{session_id}/prayer-complete/`

無 request body。僅限 `created` 或 `praying` 狀態，成功後狀態改為 `drawing`。

### 抽籤

`POST /divinations/{session_id}/draw/`

無 request body。僅限 `drawing` 狀態，隨機選出一支啟用籤詩並將狀態改為 `waiting_for_blocks`。已經抽過籤時會直接回傳原紀錄。

### 擲筊

`POST /divinations/{session_id}/blocks/`

無 request body。僅限 `waiting_for_blocks` 狀態；每一輪籤必須連續擲出 3 次聖筊。回傳：

```json
{
  "success": true,
  "data": {
    "attempt_number": 3,
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

第 3 次連續取得 `sheng` 時紀錄才改為 `confirmed`。任一次結果不是 `sheng` 時，系統立即清除該輪籤與擲筊結果、將狀態改回 `drawing`；請重新呼叫抽籤端點後開始新一輪。非聖筊回應的 `remaining_attempts` 為 `0`。

### AI 解籤

`POST /divinations/{session_id}/interpret/`

僅限已確認且有籤詩的紀錄。無 body 也可呼叫；可選擇覆寫問題與主題：

```json
{
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "divination_result": {}
}
```

成功後回傳更新後的求籤紀錄，狀態為 `completed`。AI 服務不可用時回傳 `503` 與錯誤碼 `AI_SERVICE_UNAVAILABLE`。

### AI 對話

`GET /divinations/{session_id}/chat/`

僅限已完成解籤的紀錄。回傳既有對話：

```json
{
  "success": true,
  "data": {
    "messages": [{"id": 1, "role": "user", "content": "請再說明", "created_at": "..."}],
    "remaining_messages": null
  },
  "message": "操作成功"
}
```

`POST /divinations/{session_id}/chat/`

僅限已完成解籤的紀錄。

```json
{"message": "請再說明我該注意的事項"}
```

`message` 長度為 1 至 500 字元。成功回傳 `data.reply` 與 `data.remaining_messages`。

### 標準流程

一般流程：建立紀錄 -> 完成祈求 -> 抽籤 -> 擲筊直到確認 -> AI 解籤 -> AI 對話。

## 系統與管理

### 健康檢查

`GET /health/`

不需認證。回傳 `data.status` 為 `ok`。

### 使用統計

`GET /admin/usage-stats/`

需要具有 `is_staff` 權限使用者的 JWT。回傳 `total_sessions`、`completed_sessions`，以及依 `status` 與 `category` 分組的計數。

## 非 API 管理介面

`/admin/` 是 Django Admin，供管理 SQLite 資料使用，不屬於 REST API。
