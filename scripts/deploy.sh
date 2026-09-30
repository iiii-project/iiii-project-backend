#!/usr/bin/env bash
# 正式環境部署（單台 Azure VM）：更新「這支腳本所在的 repo」並重建它自己的容器。
# 前端與後端是兩個獨立的 compose 專案，各自有一份一樣的 scripts/deploy.sh，
# 由各自 repo 的 GitHub Actions deploy job 透過 SSH 呼叫，也可以在 VM 上手動執行：
#
#   bash ~/iiii-project/iiii-project-frontend/scripts/deploy.sh
#   bash ~/iiii-project/iiii-project-backend/scripts/deploy.sh
#
# 兩邊透過共用的 docker network「iiii-project」互通，不存在時這裡會自動建立。
set -euo pipefail

# 整段包在 main() 裡、最後一行才呼叫：下面的 git pull 可能會更新這支腳本本身，
# bash 是邊讀邊執行的，先整份讀進來才不會跑到一半讀到新版內容。
main() {
  local repo name compose_file lock_file
  repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  name="$(basename "$repo")"
  compose_file="${COMPOSE_FILE_NAME:-compose.prod.yaml}"
  lock_file="${DEPLOY_LOCK_FILE:-/tmp/${name}-deploy.lock}"

  log() { printf '[deploy %s %s] %s\n' "$name" "$(date '+%F %T')" "$*"; }

  [[ -d "$repo/.git" ]] || { log "不是 git repo：$repo"; exit 1; }
  [[ -f "$repo/$compose_file" ]] || { log "找不到 $repo/$compose_file"; exit 1; }
  [[ -f "$repo/.env" ]] || { log "缺少 $repo/.env"; exit 1; }

  # 同一個 repo 手動部署與自動部署撞在一起時排隊，最多等 20 分鐘。
  exec 9>"$lock_file"
  log "等待部署鎖…"
  flock -w 1200 9 || { log "等不到部署鎖，放棄"; exit 1; }

  # --ff-only：VM 上若有人手動改過檔案就直接失敗，不會默默蓋掉；
  # .env 等設定檔都在 .gitignore 內，不受影響。
  log "更新程式碼"
  git -C "$repo" fetch --prune origin main
  git -C "$repo" checkout -q main
  git -C "$repo" pull --ff-only -q origin main
  log "  → $(git -C "$repo" log -1 --format='%h %s')"

  docker network inspect iiii-project >/dev/null 2>&1 || {
    log "建立共用網路 iiii-project"
    docker network create iiii-project >/dev/null
  }

  cd "$repo"
  log "重新建置並啟動容器"
  # --remove-orphans：拆分前前端 compose 專案裡的 backend 容器，拆分後會變成孤兒；
  # 不移除的話它會跟新的後端同時掛著同一個 SQLite volume。
  docker compose -f "$compose_file" up -d --build --force-recreate --remove-orphans

  # 每次 --build 都會留下舊的 dangling image，不清的話 VM 磁碟會慢慢被吃光。
  docker image prune -f >/dev/null

  docker compose -f "$compose_file" ps
  log "完成"
}

main "$@"
