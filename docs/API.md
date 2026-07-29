# API 文件

Base URL：`http://localhost:8000/api/v1`（本機開發；Docker Compose 部署時埠號可用 `DJANGO_PORT` 調整）

所有 API 都回傳 JSON。發送 JSON body 的請求請帶上：

```http
Content-Type: application/json
```

需要登入的端點另加上：

```http
Authorization: Bearer <access_token>
```

## 回應格式

成功回應固定為：

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

錯誤回應固定為：

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

`error.details` 的實際內容依錯誤來源而不同，請依 `error.code` 判斷：

- **欄位驗證錯誤**（`code` 固定為 `INVALID`）：`details` 是一個以欄位名稱為 key 的物件，每個 key 對應一組錯誤訊息陣列，`message` 固定為通用文字「請求無法處理」，實際錯誤內容要看 `details`。例如：
  ```json
  {
    "success": false,
    "error": {
      "code": "INVALID",
      "message": "請求無法處理",
      "details": { "question": ["此為必需欄位。"], "categories": ["此為必需欄位。"] }
    }
  }
  ```
- **業務邏輯錯誤**（例如 `INVALID_SESSION_STATE`、`FORTUNE_NOT_FOUND` 等）：`message` 是具體可讀的錯誤說明，`details` 是 `{"detail": "<與 message 相同的文字>"}`。
- **權限 / 認證錯誤**：`code` 為 `NOT_AUTHENTICATED`（401，未帶或帶了無效的 JWT）或 `PERMISSION_DENIED`（403，已登入但權限不足，或存取他人綁定的紀錄）。`NOT_AUTHENTICATED` 的 `message` 目前是 DRF 預設的英文文字（"Authentication credentials were not provided."），其餘多數錯誤訊息皆為中文，這是已知的不一致之處，前端不應依賴 `message` 的語言。
- 極少數情況（例如以完全不存在的 `session_id` 呼叫 `GET /divinations/{session_id}/`）目前會落入通用的 `INVALID_REQUEST` 代碼並帶有英文訊息，這是尚未收斂的例外處理路徑，未來可能會調整為更明確的 `NOT_FOUND`。

### 錯誤碼一覽

| code | HTTP 狀態 | 情境 |
|---|---|---|
| `INVALID` | 400 | 請求欄位驗證失敗（必填欄位缺漏、格式錯誤、選項不合法等） |
| `NOT_AUTHENTICATED` | 401 | 需要登入的端點未帶有效 JWT |
| `PERMISSION_DENIED` | 403 | 已登入但權限不足（非管理員呼叫管理端點），或未登入卻嘗試存取綁定他人帳號的求籤紀錄 |
| `NOT_FOUND` | 404 | 已登入但查詢/操作的求籤紀錄綁定的是其他使用者；`GET /divinations/{session_id}/chat/` 與 `POST /divinations/{session_id}/claim/` 另外也用此碼統一表示「不屬於本人／不存在／非匿名紀錄」這幾種情況，刻意不區分 |
| `FORTUNE_SET_NOT_FOUND` | 404 | 指定的 `fortune_set_code` 不存在，或該籤系目前非啟用中／非公開 |
| `FORTUNE_NOT_FOUND` | 404 | 指定的 `fortune_number` 在該籤系中找不到啟用中的籤詩 |
| `FORTUNE_DATA_UNAVAILABLE` | 409 | 該籤系目前沒有任何啟用中的籤詩可供抽籤 |
| `INVALID_SESSION_STATE` | 409 | 求籤紀錄目前的狀態不允許執行此操作（例如尚未擲出聖筊就要解籤） |
| `INTERPRETATION_IN_PROGRESS` | 409 | 已有另一個解籤請求正在處理中，請稍後重試 |
| `AI_SERVICE_UNAVAILABLE` | 503 | LLM 服務逾時、連線失敗或回傳空白內容 |
| `INVALID_REQUEST` | 404 | 少數未收斂的例外路徑（見上方說明） |

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

`password` 至少 8 個字元，且須通過 Django 密碼驗證規則（不可與帳號資訊過於相似、不可為常見密碼、不可為純數字）。`username` 必須唯一，重複註冊會回傳 `400`。成功時回傳 `201`：

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

`POST /auth/token/`

不需認證。

```json
{
  "username": "jimmy",
  "password": "A-strong-password-123"
}
```

成功時回傳 `{ "access": "...", "refresh": "..." }`（此端點為 djangorestframework-simplejwt 原生回應格式，不套用上方的 `success`/`data` 信封）。

### 更新 JWT

`POST /auth/token/refresh/`

不需認證。

```json
{
  "refresh": "<JWT refresh token>"
}
```

成功時回傳 `{ "access": "..." }`（同樣不套用 `success`/`data` 信封）。

### 目前使用者

`GET /auth/me/`

需要 JWT，未帶則回傳 `401 NOT_AUTHENTICATED`。

```json
{
  "success": true,
  "data": { "id": 1, "username": "jimmy", "email": "jimmy@example.com" },
  "message": "操作成功"
}
```

## 籤詩

### 籤系列表

`GET /fortune-sets/`

不需認證。僅回傳 `is_active=true` 且 `is_public=true` 的籤系，依「預設籤系優先、其餘依名稱排序」排列。

```json
{
  "success": true,
  "data": {
    "items": [
      { "code": "SIXTY_JIAZI", "name": "六十甲子籤", "description": "...", "is_default": true }
    ]
  },
  "message": "操作成功"
}
```

系統保證任一時刻最多只有一個籤系的 `is_default` 為 `true`（設定新的預設籤系時，其餘籤系會自動被取消預設）。

### 籤詩詳情

`GET /fortune-sets/{fortune_set_code}/fortunes/{number}/`

不需認證。`number` 需為正整數；只能查詢「啟用且公開籤系」中「啟用中」的籤詩，其餘情況一律回傳 `404`。

`data` 包含：`number`、`title`、`ganzhi`、`fortune_level`、`poem`、`translation`、`story`、`general_meaning`、`love_meaning`、`career_meaning`、`study_meaning`、`wealth_meaning`、`health_meaning`、`family_meaning`、`relationship_meaning`、`travel_meaning`。

## 求籤

主題 `categories` 可用值：`love`、`career`、`study`、`wealth`、`health`、`family`、`relationship`、`travel`、`other`。互動模式 `interaction_mode` 可用值：`click`、`motion`。

### 建立求籤紀錄

`POST /divinations/`

不需認證；帶有效 JWT 時紀錄會綁定登入使用者，否則為匿名紀錄。

```json
{
  "fortune_set_code": "SIXTY_JIAZI",
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "interaction_mode": "click",
  "anonymous_user_id": "browser-unique-id"
}
```

- `question`：必填，長度 2 至 300 字元。
- `categories`：必填、不可為空陣列，只能使用上方列出的值；請改用陣列，若同時帶入舊版的單數欄位 `category` 會回傳 `400`。
- `interaction_mode`：必填。
- `fortune_set_code`：選填。省略時會自動使用目前 `is_default=true` 且 `is_active=true` 的籤系（目前是 `SIXTY_JIAZI`）；若明確指定，該籤系必須同時是 `is_active=true` 且 `is_public=true`，否則回傳 `404 FORTUNE_SET_NOT_FOUND`。
- `fortune_number`：選填，正整數。指定且該編號在該籤系中確實存在啟用中的籤詩時，會**直接跳過祈求／抽籤／擲筊整個流程**，建立時就直接是 `confirmed` 狀態並綁定該籤詩；找不到對應籤詩則回傳 `404 FORTUNE_NOT_FOUND`。這是刻意保留的設計，讓已經在實體場所擲筊求得籤號的使用者可以直接輸入結果。
- `anonymous_user_id`：選填字串，用於未登入時關聯查詢自己的求籤紀錄（見下方列表端點）。

成功回傳 `201`，`data` 為求籤紀錄（格式見下）。

### 列出求籤紀錄

`GET /divinations/?anonymous_user_id={id}`

帶有效 JWT 時，回傳目前登入使用者最近 50 筆紀錄（依建立時間新到舊），**忽略** `anonymous_user_id` 參數。未登入時必須帶 `anonymous_user_id`，否則直接回傳空陣列 `{"items": []}`；帶了則回傳符合該 `anonymous_user_id` 的最近 50 筆紀錄。

### 求籤紀錄格式

所有求籤相關端點回傳的紀錄都是以下格式：

```json
{
  "session_id": "6b3e1cd9-ba83-4da3-93cc-16a0aa4e7a4d",
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

- `fortune`：確認籤詩前為 `null`；確認後採用「籤詩詳情」的欄位格式。
- `interpretation`：AI 解籤完成前為 `null`。完成後包含 `overall_meaning`（AI 回覆全文）、`relation_to_question`（目前固定為空字串，保留欄位）、`suggested_actions`（目前固定為空陣列，保留欄位）、`warnings`（固定為 `["本系統僅供文化體驗及參考。"]`）。
- `status` 目前實際會出現的值：`created` → `drawing` → `waiting_for_blocks` → `confirmed` → `interpreting`（解籤處理中的短暫過渡狀態）→ `completed`；資料庫欄位另外定義了 `praying`、`rejected`、`cancelled`，但目前程式邏輯不會產生這三個狀態。

### 讀取或刪除一筆紀錄

`GET /divinations/{session_id}/`

`DELETE /divinations/{session_id}/`

存取控制規則：
- 若該紀錄有綁定使用者：未登入會回傳 `403 PERMISSION_DENIED`；登入但不是該紀錄的擁有者會回傳 `404 NOT_FOUND`（刻意不透露紀錄存在，而非 403）。
- 若該紀錄是匿名紀錄（未綁定使用者）：任何持有 `session_id` 的人都可以讀取或刪除，不會額外檢查 `anonymous_user_id`——匿名流程的存取控制完全依賴 `session_id` 本身的不可猜測性。

刪除成功回傳 `{ "success": true, "data": {}, "message": "已刪除" }`。

### 完成祈求

`POST /divinations/{session_id}/prayer-complete/`

無 request body。僅限 `created` 狀態可呼叫，成功後狀態改為 `drawing`；非法狀態回傳 `409 INVALID_SESSION_STATE`。

### 抽籤

`POST /divinations/{session_id}/draw/`

無 request body。僅限 `drawing` 狀態；從該籤系「啟用中」的籤詩隨機抽出一支，狀態改為 `waiting_for_blocks`。若該紀錄已經抽過籤（已有 `fortune`），重複呼叫會直接原樣回傳目前紀錄，不會重抽。籤系內沒有任何啟用籤詩時回傳 `409 FORTUNE_DATA_UNAVAILABLE`。

### 擲筊

`POST /divinations/{session_id}/blocks/`

無 request body。僅限 `waiting_for_blocks` 狀態。回應：

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

`result` 可能為 `sheng`（聖筊，一正一反）、`xiao`（笑筊，兩正面）、`yin`（陰筊，兩反面）。

- 擲出 `sheng`：紀錄立即確認（`confirmed: true`、`status: "confirmed"`），`remaining_attempts` 為 `0`。
- 擲出非 `sheng`：系統會立即清除本輪的擲筊紀錄與已抽到的籤，狀態退回 `drawing`，必須重新呼叫「抽籤」端點才能再次擲筊（會抽到一支全新的籤，不是同一支籤詩重擲）。此時 `remaining_attempts` 固定回傳 `2`——這個數字**不會**隨著失敗次數遞減，因為每次沒擲出聖筊都會立刻重新抽一支新籤、歸零重算，並非在同一支籤上累積到 3 次才強制換籤。

### AI 解籤

`POST /divinations/{session_id}/interpret/`

僅限已確認（`confirmed: true`）且已有籤詩的紀錄可呼叫，否則回傳 `409 INVALID_SESSION_STATE`。無 body 也可呼叫；可選擇覆寫問題與主題（`divination_result` 欄位目前會被接受但實際上不會被使用，屬保留欄位）：

```json
{
  "question": "今年轉職是否合適？",
  "categories": ["career"],
  "divination_result": {}
}
```

- 已完成解籤（`status: "completed"` 且已有 `ai_interpretation`）時重複呼叫，會直接原樣回傳既有結果，不會重新呼叫 AI。
- 呼叫期間該紀錄狀態會短暫變為 `interpreting`；此時若有第二個請求同時打進來，會直接回傳 `409 INTERPRETATION_IN_PROGRESS`，避免重複觸發 AI 呼叫或產生重複的對話紀錄。
- 若 AI 服務呼叫失敗（逾時、連線錯誤、回傳空白），回傳 `503 AI_SERVICE_UNAVAILABLE`，紀錄狀態會還原成呼叫前的狀態，可以直接重新呼叫本端點重試。
- 成功後回傳更新後的求籤紀錄，`status` 為 `completed`。

### 認領匿名紀錄

`POST /divinations/{session_id}/claim/`

需要 JWT，無 request body。用途：使用者先以匿名方式（例如掃 QR Code）完成解籤，事後登入時將該筆匿名紀錄綁定到自己的帳號，才能使用上面「AI 對話」的 `GET` 端點讀回對話紀錄。

- 僅可認領 `user` 為 `null` 的匿名紀錄；`session_id` 本身就是匿名流程的持有憑證，不另外檢查 `anonymous_user_id`。
- 認領成功時，將 `user` 設為目前 JWT 對應的使用者，並將 `anonymous_user_id` 清空。
- 若紀錄已經是目前使用者本人所擁有，直接回傳成功與目前紀錄，不重複寫入，前端可安全重試。
- 若 `session_id` 不存在、已綁定其他使用者、或已不是匿名紀錄（例如登入時直接建立），一律回傳相同的 `404 NOT_FOUND`，避免洩漏紀錄是否存在或其擁有權：
  ```json
  {
    "success": false,
    "error": {
      "code": "NOT_FOUND",
      "message": "找不到這次求籤紀錄",
      "details": { "detail": "找不到這次求籤紀錄" }
    }
  }
  ```
- 不限制紀錄的 `status`；認領本身與解籤流程進度無關。
- 認領在資料庫 transaction 中鎖定該筆紀錄後才寫入，避免兩個帳號同時認領同一筆匿名紀錄。

成功回傳 `200`，`data` 為認領後的求籤紀錄（格式同「求籤紀錄格式」）：

```json
{
  "success": true,
  "data": {
    "session_id": "6b3e1cd9-ba83-4da3-93cc-16a0aa4e7a4d",
    "user": 1,
    "anonymous_user_id": "",
    "fortune_set": { "code": "SIXTY_JIAZI", "name": "六十甲子籤", "description": "...", "is_default": true },
    "fortune": {},
    "question": "今年轉職是否合適？",
    "categories": ["career"],
    "interaction_mode": "click",
    "status": "completed",
    "confirmed": true,
    "interpretation": {},
    "ai_interpretation": "...",
    "created_at": "2026-07-14T00:00:00Z",
    "updated_at": "2026-07-14T00:05:00Z",
    "completed_at": "2026-07-14T00:04:00Z"
  },
  "message": "操作成功"
}
```

### AI 對話

`GET /divinations/{session_id}/chat/`

**需要 JWT，且僅回傳登入使用者本人擁有的紀錄**（STORY-003 起生效；`user` 欄位由建立 session 當下的 JWT 決定，之後才登入不會回溯取得擁有權）：

- 未帶或帶無效 JWT：回傳 `401 NOT_AUTHENTICATED`。
  ```json
  {
    "success": false,
    "error": {
      "code": "NOT_AUTHENTICATED",
      "message": "Authentication credentials were not provided.",
      "details": { "detail": "Authentication credentials were not provided." }
    }
  }
  ```
- 已登入但 `session_id` 不屬於目前使用者、或該 `session_id` 根本不存在、或該紀錄是匿名建立（沒有綁定任何使用者）：一律回傳 `404 NOT_FOUND`，**回應內容與狀態碼在這三種情況下逐字元完全相同**，不會透露 `session_id` 是否存在：
  ```json
  {
    "success": false,
    "error": {
      "code": "NOT_FOUND",
      "message": "找不到這次求籤紀錄",
      "details": { "detail": "找不到這次求籤紀錄" }
    }
  }
  ```
- 已登入且是本人擁有的紀錄，但尚未完成解籤：回傳 `409 INVALID_SESSION_STATE`（此情況已透過擁有權驗證，不受上面的匿名化規則限制）。
- 已登入、是本人擁有、且已完成解籤：回傳 `200`，內容為目前的對話紀錄（不含解籤當下產生、對使用者隱藏的初始 prompt 與回覆）：

```json
{
  "success": true,
  "data": {
    "messages": [
      { "id": 5, "role": "user", "content": "請再說明", "created_at": "2026-07-14T00:05:00Z" },
      { "id": 6, "role": "assistant", "content": "...", "created_at": "2026-07-14T00:05:03Z" }
    ],
    "remaining_messages": null
  },
  "message": "操作成功"
}
```

> 注意：因為此端點現在要求登入，**匿名建立的求籤紀錄無法透過 GET 讀回對話紀錄**，即使是該紀錄的原始建立者也一樣（沒有登入就沒有「本人」可言）。匿名流程仍可透過下方的 `POST` 端點取得單次回覆內容（回覆會包含在 POST 的回應裡），只是不能事後用 GET 重新查閱完整對話。

`POST /divinations/{session_id}/chat/`

僅限已完成解籤的紀錄，且此端點會依「讀取或刪除一筆紀錄」的相同規則檢查擁有權。

```json
{ "message": "請再說明我該注意的事項" }
```

`message` 長度為 1 至 500 字元。成功回傳：

```json
{
  "success": true,
  "data": {
    "reply": "...",
    "messages": [ /* 與 GET 端點相同格式，包含這次新增的一問一答 */ ],
    "remaining_messages": null
  },
  "message": "操作成功"
}
```

`remaining_messages` 目前在 GET 與 POST 都固定回傳 `null`，是為未來可能加入的對話次數限制保留的欄位，目前沒有實際限制。

### 標準流程

建立紀錄 → 完成祈求 → 抽籤 → 擲筊直到擲出聖筊（未中則重新抽籤） → AI 解籤 → AI 對話。若建立時直接帶 `fortune_number`，則會跳過「完成祈求 → 抽籤 → 擲筊」直接進入已確認狀態。

若求籤是匿名建立的（QR Code 流程），使用者想私人追問時需先登入，再呼叫「認領匿名紀錄」將該筆紀錄綁定到帳號，才能使用 `GET /divinations/{session_id}/chat/` 讀回對話紀錄。

## 管理員 API

以下端點都需要 `is_staff=true` 使用者的 JWT；未登入回傳 `401 NOT_AUTHENTICATED`，已登入但非管理員回傳 `403 PERMISSION_DENIED`。

### 籤詩批次匯入 / 更新

`POST /admin/fortune-sets/{fortune_set_code}/fortunes/import/`

`items` 內每筆資料會依 `number` 建立或更新該籤系底下的籤詩；整批資料在同一個 transaction 中寫入，只要其中一筆驗證失敗，就不會寫入任何一筆（整批回滾），並回傳 `400 INVALID`。

```json
{
  "items": [
    {
      "number": 1,
      "title": "第一籤",
      "poem": "籤詩內容",
      "translation": "白話解釋",
      "fortune_level": "上吉"
    }
  ]
}
```

`number`、`poem` 為必填欄位；其餘可用欄位與「籤詩詳情」相同，另可帶 `source_reference`、`is_active`。成功回傳 `{ "imported": <筆數> }`。

### 使用統計

`GET /admin/usage-stats/`

回傳 `total_sessions`、`completed_sessions`，以及依 `status`、`category` 分組的求籤紀錄計數。

## 系統

### 健康檢查

`GET /health/`

不需認證。回傳 `data.status` 為 `"ok"`，僅用於確認服務存活，不做任何資料庫或外部服務檢查。

## 非 API 管理介面

`/admin/` 是 Django Admin，供管理 SQLite 資料使用，不屬於本文件描述的 REST API，也不套用上方的回應信封格式。
