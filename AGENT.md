# AI 求籤互動系統－後端開發規範

本文件供後端開發者與 AI Agent 使用，目的是統一 Django 後端的架構、API、資料模型、服務層、SQLite、AI 串接與測試方式。

若需求與本文件衝突，以最新且明確的人類需求為優先，完成後應同步更新本文件。

---

# 1. 專案定位

系統名稱：AI 求籤互動系統

後端負責：

- 籤系與籤詩資料
- 求籤工作階段
- 抽籤結果
- 擲筊結果
- 流程狀態
- AI 解籤與聊天
- 歷史紀錄
- 管理者權限
- Django Admin
- 系統設定與日誌

第一階段使用六十甲子籤，但資料模型必須支援未來新增其他籤系。

---

# 2. 固定技術棧

除非需求明確變更，禁止自行更換：

- Python 3.12
- Django
- Django REST Framework
- Django ORM
- Django Migration
- Django Admin
- SQLite
- Simple JWT
- django-cors-headers
- django-filter
- HTTPX
- pytest
- pytest-django

禁止自行改用 FastAPI、Flask、SQLAlchemy 或 PostgreSQL。

---

# 3. 後端目錄結構

```text
backend/
├── AGENT.md
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/
│   ├── fortunes/
│   ├── divinations/
│   ├── ai_service/
│   └── system/
├── data/
│   └── ai_fortune.sqlite3
├── logs/
├── static/
├── media/
├── tests/
├── requirements.txt
└── .env
```

---

# 4. Django App 分工

## accounts

- 管理者帳號
- 登入驗證
- JWT
- 權限

## fortunes

- FortuneSet
- Fortune
- 六十甲子籤
- 籤詩 CRUD
- 籤詩匯入
- 籤詩啟用與停用

## divinations

- DivinationSession
- BlockCast
- 抽籤
- 擲筊
- 流程狀態
- 歷史紀錄

## ai_service

- AIMessage
- 提示詞
- LLM Client
- AI 解籤
- AI 聊天
- 回應解析
- AI 錯誤處理

## system

- SystemSetting
- SystemLog
- 使用統計
- 健康檢查

---

# 5. Python 程式風格

- 遵守 PEP 8
- 公開函式盡量加 type hints
- 類別使用 PascalCase
- 函式、變數、檔名使用 snake_case
- 常數使用 UPPER_SNAKE_CASE
- 使用 early return
- 不保留註解掉的廢棄程式碼
- 不留下未使用 import
- 不使用模糊名稱，如 `data`、`info`、`temp`

---

# 6. 分層原則

## Model

負責：

- 資料結構
- 關聯
- 基礎約束
- Choice
- UniqueConstraint

## Serializer

負責：

- 輸入驗證
- 輸出序列化
- 欄位白名單
- 格式轉換

## View / ViewSet

負責：

- 接收 Request
- 呼叫 Service
- 回傳 Response
- 權限判斷

不得放置大量商業邏輯。

## Service

負責：

- 抽籤
- 擲筊
- 流程狀態轉換
- AI 解籤
- AI 聊天
- 複合資料操作

Service 不得直接回傳 DRF Response。

---

# 7. API 規範

API 基底：

```text
/api/v1/
```

命名原則：

- 小寫
- 複數名詞
- kebab-case
- 尾端保留 `/`

主要端點：

```text
GET  /api/v1/fortune-sets/
POST /api/v1/divinations/
POST /api/v1/divinations/{session_id}/prayer-complete/
POST /api/v1/divinations/{session_id}/draw/
POST /api/v1/divinations/{session_id}/blocks/
POST /api/v1/divinations/{session_id}/interpret/
POST /api/v1/divinations/{session_id}/chat/
GET  /api/v1/divinations/?anonymous_user_id={id}
GET  /api/v1/divinations/{session_id}/
DELETE /api/v1/divinations/{session_id}/
```

---

# 8. API 回應格式

成功：

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

失敗：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_SESSION_STATE",
    "message": "目前狀態不可執行此操作",
    "details": null
  }
}
```

錯誤代碼使用大寫 snake case。

常用錯誤：

- INVALID_SESSION_STATE
- DIVINATION_ALREADY_DRAWN
- BLOCK_CAST_LIMIT_REACHED
- FORTUNE_SET_NOT_FOUND
- FORTUNE_DATA_UNAVAILABLE
- AI_SERVICE_UNAVAILABLE
- INVALID_REQUEST

---

# 9. 資料模型規範

## FortuneSet

必須包含：

- code
- name
- description
- source_name
- version
- prompt_template
- is_default
- is_public
- is_active
- created_at
- updated_at

預設籤系：

```text
code = SIXTY_JIAZI
name = 六十甲子籤
```

## Fortune

必須屬於 FortuneSet。

同一籤系內籤號不可重複：

```text
UNIQUE(fortune_set, number)
```

不可將抽籤邏輯寫死為 1 至 60。

## DivinationSession

必須包含：

- session_uuid
- anonymous_user_id
- fortune_set
- fortune
- question
- category
- interaction_mode
- status
- confirmed
- ai_interpretation
- created_at
- updated_at
- completed_at

## BlockCast

- 每次擲筊都保存
- 最多三次
- 取得聖筊後不可再擲筊

## AIMessage

角色固定：

- system
- user
- assistant

不同工作階段的對話不得混用。

---

# 10. 流程狀態規範

固定狀態：

```text
created
praying
drawing
waiting_for_blocks
confirmed
rejected
interpreting
completed
cancelled
```

建議轉換：

```text
created
→ praying
→ drawing
→ waiting_for_blocks
→ confirmed
→ interpreting
→ completed
```

或：

```text
waiting_for_blocks
→ rejected
```

狀態由後端控制。

不得允許前端直接指定 status。

---

# 11. Serializer 驗證規範

必須驗證：

- question 長度 2 至 300 字
- category 是否為允許值
- interaction_mode 是否為 click 或 motion
- fortune_set_code 是否存在且啟用
- chat message 不得超過 500 字

前端不得提交或修改：

- fortune
- confirmed
- status
- ai_interpretation
- block_one
- block_two
- result

上述欄位只能由 Service 控制。

---

# 12. 抽籤規範

- 查詢目前籤系中 `is_active=True` 的籤詩
- 每個工作階段只可抽籤一次
- 重複呼叫時回傳原籤
- 抽籤結果必須寫入資料庫
- 使用 Service 層
- 使用短 transaction
- 不得信任前端傳入 fortune_id
- 不得寫死 1 到 60

---

# 13. 擲筊規範

筊杯組合：

```text
flat + round = sheng
round + flat = sheng
flat + flat = xiao
round + round = yin
```

規則：

- 結果由後端產生
- 每次結果都保存
- 最大次數為 3
- 取得聖筊後 `confirmed=True`
- 取得聖筊後不得再次擲筊
- 三次未取得聖筊，狀態改為 rejected

---

# 14. AI 解籤規範

AI 至少接收：

- 籤系名稱
- 使用者問題
- 求籤主題
- 籤號
- 籤名
- 天干地支
- 吉凶分類
- 籤詩原文
- 白話翻譯
- 籤詩典故
- 一般解釋
- 對應主題解釋
- 擲筊結果

回答應包含：

1. 籤詩整體含義
2. 與問題的關聯
3. 當前情況分析
4. 可採取的行動
5. 應注意事項
6. 文化體驗提醒

AI 不得：

- 宣稱未來一定會發生
- 宣稱代表神明
- 預測死亡
- 鼓勵自我傷害
- 提供違法建議
- 取代醫療、法律或財務專業意見
- 虛構籤詩原文或典故
- 混用其他籤系資料
- 使用恐嚇或詛咒語氣

---

# 15. AI API 呼叫規範

- 使用 HTTPX
- 必須設定 timeout
- 必須處理連線失敗
- 必須處理非 2xx 回應
- 不得在 transaction 中等待 LLM
- AI 失敗時保留求籤資料
- AI 失敗時回傳可理解錯誤
- API Key 只能放 `.env`
- 前端不得取得 API Key

---

# 16. Transaction 規範

使用 `transaction.atomic`：

- 抽籤
- 擲筊
- 大量匯入籤詩
- 刪除完整工作階段
- 儲存 AI 最終結果

禁止在 transaction 中執行：

- LLM API 呼叫
- 大型檔案處理
- 不可預期的外部請求

---

# 17. SQLite 規範

- 使用 Django ORM
- 資料庫檔案：`backend/data/ai_fortune.sqlite3`
- 設定 timeout
- 保持 transaction 短小
- 避免高頻率長時間寫入
- 每日備份
- 至少保留最近 7 份
- 使用 SQLite Backup API
- 不直接複製正在寫入的資料庫

目前不得自行改用 PostgreSQL。

---

# 18. Django Admin 規範

第一階段管理後台使用 Django Admin。

至少可管理：

- FortuneSet
- Fortune
- DivinationSession
- BlockCast
- AIMessage
- SystemSetting
- SystemLog

Admin 顯示欄位需清楚，避免只顯示物件 ID。

重要欄位應支援：

- 搜尋
- 篩選
- 啟用 / 停用
- 日期排序

---

# 19. 安全規範

- `.env` 不得提交 Git
- `DJANGO_SECRET_KEY` 不得寫死
- 正式環境 `DEBUG=False`
- CORS 不得全開
- 管理 API 必須驗證權限
- 使用 Django 密碼雜湊
- 輸入必須經 Serializer 驗證
- 錯誤回應不得暴露堆疊、資料庫路徑、秘密
- 不接受前端傳入核心結果欄位
- API Key 不得寫入原始碼

---

# 20. 測試規範

使用：

- Django TestCase
- DRF APITestCase
- pytest
- pytest-django

必須測試：

- 只能抽到啟用籤詩
- 重複抽籤結果一致
- 擲筊最多三次
- 聖筊後不可再擲筊
- 未確認不可 AI 解籤
- 同一籤系不可有重複籤號
- 刪除工作階段後關聯資料同步刪除
- AI 失敗時資料不遺失
- 管理 API 權限正確
- 狀態跳轉非法時回傳錯誤

---

# 21. 日誌規範

至少記錄：

- API 錯誤
- 抽籤失敗
- 擲筊狀態錯誤
- AI 呼叫失敗
- 資料匯入失敗
- 權限錯誤

日誌不得保存：

- 密碼
- API Key
- 完整 JWT
- 不必要的敏感個資

---

# 22. Migration 規範

- 修改 Model 必須建立 Migration
- 不得手動修改 SQLite 結構取代 Migration
- Migration 名稱要清楚
- 刪除欄位前應評估資料遷移
- Agent 修改 Model 後必須回報是否新增 Migration

---

# 23. Agent 工作流程

每次後端修改應：

1. 先閱讀本文件
2. 檢查既有 Model、Serializer、Service、View
3. 避免重複建立功能
4. 以最小必要修改完成需求
5. 補上輸入驗證與錯誤處理
6. 評估是否需要 Migration
7. 補上測試
8. 執行測試
9. 回報修改檔案、Migration、環境變數與測試結果

---

# 24. Agent 禁止事項

不得：

- 改用 FastAPI
- 改用 Flask
- 改用 SQLAlchemy
- 改用 PostgreSQL
- 把商業邏輯塞入 View
- 在前端產生核心結果
- 把 API Key 寫入程式碼
- 在 transaction 中等待 AI
- 信任前端傳入 fortune、status、result
- 無需求時大量重構
- 修改 Model 卻不建立 Migration
- 刪除資料欄位卻不說明風險
- 將不同籤系資料混用

---

# 25. 完成定義

後端功能只有在以下條件皆符合時才算完成：

- API 可正常使用
- Serializer 驗證完整
- Service 層邏輯清楚
- 核心狀態由後端控制
- Transaction 使用正確
- AI 錯誤有處理
- SQLite 操作安全
- 權限正確
- 核心測試通過
- 必要 Migration 已建立
- 不洩漏敏感資料
