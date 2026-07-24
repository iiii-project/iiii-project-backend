#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

SERVER="${LLAMA_SERVER:-$SCRIPT_DIR/llama-server}"
MODEL_DIR="$SCRIPT_DIR/../model"

HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-1234}"

# 你的硬體建議值：
# 8192 總 context ÷ 2 個平行 slot ≈ 每個請求 4096
CONTEXT_SIZE="8192"
PARALLEL="1"

# 降低一次處理量，減少 6GB VRAM 壓力
BATCH_SIZE="512"
UBATCH_SIZE="256"

pause_and_exit() {
    local exit_code="${1:-1}"
    echo
    if [ -t 0 ]; then
        read -rp "按 Enter 關閉..."
    fi
    exit "$exit_code"
}

# ---------- 基本檢查 ----------

if [ ! -x "$SERVER" ]; then
    echo "找不到可執行的 llama-server："
    echo "$SERVER"
    pause_and_exit 1
fi

if [ ! -d "$MODEL_DIR" ]; then
    echo "找不到模型資料夾："
    echo "$MODEL_DIR"
    pause_and_exit 1
fi

# 檢查 Port 是否已被占用
if command -v ss >/dev/null 2>&1; then
    if ss -ltn | awk '{print $4}' | grep -qE "[:.]${PORT}$"; then
        echo "Port $PORT 已經被使用。"
        echo
        echo "可能已有另一個 llama-server 正在執行。"
        echo "請先關閉舊的伺服器，再重新啟動。"
        pause_and_exit 1
    fi
fi

# ---------- 搜尋主模型 ----------

# 排除：
# 1. mmproj 視覺投影檔
# 2. TranslateGemma，因為它有獨立的翻譯腳本
# 3. 多分片模型中非第一片的檔案
mapfile -d '' MODELS < <(
    find "$MODEL_DIR" -type f -iname "*.gguf" \
        ! -iname "*mmproj*" \
        ! -iname "*translategemma*" \
        ! -iname "*translate-gemma*" \
        ! -regex '.*-[0-9][0-9][0-9][0-9][0-9]-of-[0-9][0-9][0-9][0-9][0-9]\.gguf$' \
        -print0 |
        sort -z
)

# 把多分片模型的第一片補回來
mapfile -d '' SHARD_MODELS < <(
    find "$MODEL_DIR" -type f \
        -iname "*-00001-of-*.gguf" \
        ! -iname "*mmproj*" \
        ! -iname "*translategemma*" \
        ! -iname "*translate-gemma*" \
        -print0 |
        sort -z
)

if [ "${#SHARD_MODELS[@]}" -gt 0 ]; then
    MODELS+=("${SHARD_MODELS[@]}")
fi

if [ "${#MODELS[@]}" -eq 0 ]; then
    echo "找不到可用的 GGUF 主模型。"
    echo
    echo "搜尋位置："
    echo "$MODEL_DIR"
    pause_and_exit 1
fi

# ---------- 自動選擇模型 ----------

MODEL=""
if [ -z "${LLAMA_MODEL:-}" ]; then
    MODEL="${MODELS[0]}"
elif [[ "$LLAMA_MODEL" =~ ^[0-9]+$ ]] && [ "$LLAMA_MODEL" -gt 0 ] && [ "$LLAMA_MODEL" -le "${#MODELS[@]}" ]; then
    MODEL="${MODELS[$((LLAMA_MODEL - 1))]}"
else
    for candidate in "${MODELS[@]}"; do
        if [ "$candidate" = "$LLAMA_MODEL" ] || [ "$(basename "$candidate")" = "$LLAMA_MODEL" ]; then
            MODEL="$candidate"
            break
        fi
    done
fi

if [ -z "$MODEL" ]; then
    echo "找不到指定的模型：${LLAMA_MODEL:-}"
    pause_and_exit 1
fi

MODEL_FOLDER="$(dirname "$MODEL")"
MODEL_FILENAME="$(basename "$MODEL")"

ALIAS="${LLAMA_MODEL_ALIAS:-${MODEL_FILENAME%.gguf}}"

# 多分片模型的 API 名稱移除片號
ALIAS="$(printf '%s' "$ALIAS" |
    sed -E 's/-00001-of-[0-9]+$//')"

# ---------- 自動搜尋 mmproj ----------

MMPROJ=""

mapfile -d '' MMPROJ_FILES < <(
    find "$MODEL_FOLDER" -maxdepth 1 -type f \
        \( -iname "mmproj*.gguf" -o -iname "*mmproj*.gguf" \) \
        -print0 |
        sort -z
)

if [ "${#MMPROJ_FILES[@]}" -eq 1 ]; then
    # 同資料夾只有一個 mmproj，直接使用
    MMPROJ="${MMPROJ_FILES[0]}"

elif [ "${#MMPROJ_FILES[@]}" -gt 1 ]; then
    # 移除模型檔名中的量化標記，用來配對 mmproj
    MODEL_BASE="$ALIAS"

    MODEL_BASE="$(printf '%s' "$MODEL_BASE" |
        sed -E \
        's/[._-](Q[0-9]+(_[A-Z0-9]+)*|IQ[0-9]+(_[A-Z0-9]+)*|F16|BF16|FP16|MXFP4)$//I')"

    MODEL_BASE_LOWER="$(printf '%s' "$MODEL_BASE" |
        tr '[:upper:]' '[:lower:]')"

    for FILE in "${MMPROJ_FILES[@]}"; do
        FILE_LOWER="$(basename "$FILE" |
            tr '[:upper:]' '[:lower:]')"

        if [[ "$FILE_LOWER" == *"$MODEL_BASE_LOWER"* ]]; then
            MMPROJ="$FILE"
            break
        fi
    done
fi

EXTRA_ARGS=()

if [ -n "$MMPROJ" ]; then
    EXTRA_ARGS+=(
        --mmproj "$MMPROJ"
    )
fi

# ---------- 顯示啟動設定 ----------

echo
echo "主模型：$MODEL_FILENAME"

if [ -n "$MMPROJ" ]; then
    echo "圖片模型：$(basename "$MMPROJ")"
    echo "模式：文字＋圖片"
else
    echo "圖片模型：未找到"
    echo "模式：純文字"
fi

echo
echo "API 模型名稱：$ALIAS"
echo "總 Context：$CONTEXT_SIZE"
echo "平行請求數：$PARALLEL"
echo "每個 Slot 約可用：$((CONTEXT_SIZE / PARALLEL)) tokens"
echo
echo "網頁：http://$HOST:$PORT"
echo "API Base URL：http://$HOST:$PORT/v1"
echo
echo "停止伺服器請按 Ctrl+C"
echo

# ---------- 啟動 llama-server ----------

"$SERVER" \
    --model "$MODEL" \
    --alias "$ALIAS" \
    --host "$HOST" \
    --port "$PORT" \
    --ctx-size "$CONTEXT_SIZE" \
    --parallel "$PARALLEL" \
    --batch-size "$BATCH_SIZE" \
    --ubatch-size "$UBATCH_SIZE" \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --flash-attn auto \
    --n-predict 1024 \
    "${EXTRA_ARGS[@]}" &

SERVER_PID=$!

cleanup() {
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        echo
        echo "正在停止 llama-server..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

# ---------- 等待啟動完成 ----------

READY=0

for ((i = 1; i <= 240; i++)); do
    if curl -fsS "http://$HOST:$PORT/health" >/dev/null 2>&1; then
        READY=1
        break
    fi

    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo
        echo "llama-server 啟動失敗。"
        pause_and_exit 1
    fi

    sleep 1
done

if [ "$READY" -ne 1 ]; then
    echo
    echo "等待模型啟動逾時。"
    pause_and_exit 1
fi

echo
echo "========================================"
echo "llama-server 已成功啟動"
echo "========================================"
echo
echo "網頁：http://$HOST:$PORT"
echo "API：http://$HOST:$PORT/v1"
echo "模型：$ALIAS"
echo
echo "健康檢查："
echo "curl http://$HOST:$PORT/health"
echo
echo "模型清單："
echo "curl http://$HOST:$PORT/v1/models"
echo
echo "伺服器正在執行，按 Ctrl+C 停止。"
echo

xdg-open "http://$HOST:$PORT" >/dev/null 2>&1 || true

wait "$SERVER_PID"
