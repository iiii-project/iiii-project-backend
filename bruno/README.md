# Bruno API Collection

在 Bruno 開啟 `bruno/`，選擇 `local` environment。

`fortuneNumber` 必須是 `fortuneSetCode` 中已啟用的籤號。`username` 與 `email` 必須是尚未註冊的值，才能執行 Auth 的 Register request。`adminAccessToken` 必須是 staff 使用者的 JWT，才能執行 Admin request。

建議依序執行：Health、Fortunes、Divinations、AI、Auth，最後才執行 Admin。Divinations 與 AI request 使用 runtime-only variables 串接 session ID，測試結束會刪除建立的 session。AI request 需要可用的 LLM 服務。

CLI 範例：

```bash
npx @usebruno/cli run "03 Divinations" "04 AI" --env local
```
