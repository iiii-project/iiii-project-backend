# 匿名解籤紀錄認領 API 規格

## 目的

使用者可先透過 QR Code 匿名完成解籤；在點選「私人追問」並完成登入後，將該筆匿名解籤紀錄綁定至目前登入帳號。認領成功後，前端即可使用既有的私人對話 API：

- `GET /divinations/{session_id}/chat/`
- `POST /divinations/{session_id}/chat/`

## 端點

`POST /divinations/{session_id}/claim/`

需要 JWT：

```http
Authorization: Bearer <access_token>
```

不需要 request body。

## 認領規則

1. 以 URL 中的 `session_id` 尋找求籤紀錄。
2. 僅可認領 `user=null` 的匿名紀錄。
3. `session_id` 是匿名流程的持有憑證；不另要求 `anonymous_user_id`。
4. 認領成功時，將紀錄的 `user` 設為目前 JWT 對應的使用者，並將 `anonymous_user_id` 清為 `null`。
5. 清除 `anonymous_user_id` 可避免該筆已認領紀錄繼續出現在匿名紀錄列表中。
6. 若紀錄已屬於目前使用者，回傳成功與目前紀錄，不重複寫入，讓前端重試安全。
7. 若紀錄已屬於其他使用者、`session_id` 不存在，或不再是匿名紀錄，一律回傳相同的 `404 NOT_FOUND`，避免洩漏紀錄存在或擁有權。
8. 認領需在 transaction 中完成，並鎖定該筆紀錄，避免兩個帳號同時認領成功。
9. 不限制紀錄狀態；前端僅在解籤完成、使用者要私人追問時呼叫。後端保留此彈性，避免中斷中的流程無法恢復。

## 成功回應

HTTP `200`：

```json
{
  "success": true,
  "data": {
    "session_id": "6b3e1cd9-ba83-4da3-93cc-16a0aa4e7a4d",
    "user": { "id": 1, "username": "jimmy", "email": "jimmy@example.com" },
    "anonymous_user_id": null,
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

`data` 沿用既有「求籤紀錄格式」的完整欄位；以上以 `{}` 與 `...` 簡化巢狀內容。

## 失敗回應

未登入或 JWT 無效時，回傳 HTTP `401` 與既有 `NOT_AUTHENTICATED` 格式。

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

紀錄不存在，或已被其他帳號認領時，統一回傳 HTTP `404`：

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

## 前端串接流程

1. 使用者掃描 QR Code，匿名完成解籤。
2. 使用者點選「私人追問」。
3. 若尚未登入，前端導向註冊或登入；登入成功後保留原本的 `session_id`。
4. 前端以 JWT 呼叫 `POST /divinations/{session_id}/claim/`。
5. 成功後呼叫 `GET /divinations/{session_id}/chat/` 載入私人對話，並開放 `POST /divinations/{session_id}/chat/` 追問。
6. 收到 `404 NOT_FOUND` 時，提示使用者此解籤紀錄無法認領，並返回解籤結果或首頁。
