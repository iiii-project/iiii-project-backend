#requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ============================================================
# 基本路徑設定
# ============================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Server = Join-Path $ScriptDir "llama-b9873\llama-server.exe"

# 修改成你的 Windows 模型資料夾
$ModelDir = "D:\models"

$HostAddress = "127.0.0.1"
$Port = 1234

# 8192 總 Context，PARALLEL=1 時單一請求最多約 8192 tokens
$ContextSize = 8192
$Parallel = 1

# 降低一次處理量，減少 6GB VRAM 壓力
$BatchSize = 512
$UBatchSize = 256

$ServerProcess = $null

# ============================================================
# 共用函式
# ============================================================

function Pause-AndExit {
    param(
        [int]$ExitCode = 1
    )

    Write-Host ""
    Read-Host "按 Enter 關閉"
    exit $ExitCode
}

function Stop-LlamaServer {
    if ($null -ne $script:ServerProcess) {
        try {
            if (-not $script:ServerProcess.HasExited) {
                Write-Host ""
                Write-Host "正在停止 llama-server..."

                Stop-Process `
                    -Id $script:ServerProcess.Id `
                    -Force `
                    -ErrorAction SilentlyContinue

                $script:ServerProcess.WaitForExit()
            }
        }
        catch {
            # 關閉階段不再拋出錯誤
        }
    }
}

# 發生未處理錯誤時，確保 llama-server 被停止
trap {
    Write-Host ""
    Write-Host "發生錯誤：$($_.Exception.Message)" -ForegroundColor Red

    Stop-LlamaServer
    Pause-AndExit 1
}

# ============================================================
# 基本檢查
# ============================================================

if (-not (Test-Path -LiteralPath $Server -PathType Leaf)) {
    Write-Host "找不到 llama-server.exe：" -ForegroundColor Red
    Write-Host $Server
    Pause-AndExit 1
}

if (-not (Test-Path -LiteralPath $ModelDir -PathType Container)) {
    Write-Host "找不到模型資料夾：" -ForegroundColor Red
    Write-Host $ModelDir
    Pause-AndExit 1
}

# ============================================================
# 檢查 Port 是否已被占用
# ============================================================

$PortInUse = $false

try {
    $Connection = Get-NetTCPConnection `
        -LocalPort $Port `
        -State Listen `
        -ErrorAction SilentlyContinue

    if ($null -ne $Connection) {
        $PortInUse = $true
    }
}
catch {
    # 某些舊版 Windows 或權限不足時，改用 netstat
    $NetstatResult = netstat -ano |
        Select-String -Pattern "[:.]$Port\s+.*LISTENING"

    if ($null -ne $NetstatResult) {
        $PortInUse = $true
    }
}

if ($PortInUse) {
    Write-Host "Port $Port 已經被使用。" -ForegroundColor Red
    Write-Host ""
    Write-Host "可能已有另一個 llama-server 正在執行。"
    Write-Host "請先關閉舊的伺服器，再重新啟動。"

    Pause-AndExit 1
}

# ============================================================
# 搜尋主模型
# ============================================================

# 排除：
# 1. mmproj 視覺投影檔
# 2. TranslateGemma，因為它有獨立翻譯腳本
# 3. 多分片模型中非第一片的檔案

$AllGGUFFiles = @(
    Get-ChildItem `
        -LiteralPath $ModelDir `
        -Filter "*.gguf" `
        -File `
        -Recurse `
        -ErrorAction SilentlyContinue
)

$Models = @(
    $AllGGUFFiles |
        Where-Object {
            $Name = $_.Name

            $IsMMProj = $Name -match "(?i)mmproj"
            $IsTranslateGemma = $Name -match "(?i)translate-?gemma"

            # 所有分片模型先排除，後面只補回第一片
            $IsShard = $Name -match "-\d{5}-of-\d{5}\.gguf$"

            (-not $IsMMProj) -and
            (-not $IsTranslateGemma) -and
            (-not $IsShard)
        } |
        Sort-Object FullName
)

# 把多分片模型的第一片補回來
$ShardModels = @(
    $AllGGUFFiles |
        Where-Object {
            $Name = $_.Name

            $IsFirstShard = $Name -match "-00001-of-\d{5}\.gguf$"
            $IsMMProj = $Name -match "(?i)mmproj"
            $IsTranslateGemma = $Name -match "(?i)translate-?gemma"

            $IsFirstShard -and
            (-not $IsMMProj) -and
            (-not $IsTranslateGemma)
        } |
        Sort-Object FullName
)

if ($ShardModels.Count -gt 0) {
    $Models = @($Models + $ShardModels)
}

$Models = @(
    $Models |
        Sort-Object FullName -Unique
)

if ($Models.Count -eq 0) {
    Write-Host "找不到可用的 GGUF 主模型。" -ForegroundColor Red
    Write-Host ""
    Write-Host "搜尋位置："
    Write-Host $ModelDir

    Pause-AndExit 1
}

# ============================================================
# 模型選單
# ============================================================

Write-Host "請選擇要啟動的模型："
Write-Host ""

for ($i = 0; $i -lt $Models.Count; $i++) {
    $ModelFile = $Models[$i]

    $SizeGB = $ModelFile.Length / 1GB

    if ($SizeGB -ge 1) {
        $ModelSize = "{0:N2} GB" -f $SizeGB
    }
    else {
        $ModelSize = "{0:N0} MB" -f ($ModelFile.Length / 1MB)
    }

    Write-Host (
        "{0,2}) {1,-60} [{2}]" -f `
            ($i + 1),
            $ModelFile.Name,
            $ModelSize
    )
}

Write-Host ""
$Choice = Read-Host "輸入編號"

[int]$ChoiceNumber = 0

if (-not [int]::TryParse($Choice, [ref]$ChoiceNumber)) {
    Write-Host "請輸入有效的數字。" -ForegroundColor Red
    Pause-AndExit 1
}

$Index = $ChoiceNumber - 1

if ($Index -lt 0 -or $Index -ge $Models.Count) {
    Write-Host "沒有這個模型編號。" -ForegroundColor Red
    Pause-AndExit 1
}

$Model = $Models[$Index]

$ModelFolder = $Model.DirectoryName
$ModelFilename = $Model.Name

$Alias = [System.IO.Path]::GetFileNameWithoutExtension($ModelFilename)

# 多分片模型的 API 名稱移除片號
$Alias = $Alias -replace "-00001-of-\d+$", ""

# ============================================================
# 自動搜尋 mmproj
# ============================================================

$MMProj = $null

$MMProjFiles = @(
    Get-ChildItem `
        -LiteralPath $ModelFolder `
        -Filter "*.gguf" `
        -File `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match "(?i)mmproj"
        } |
        Sort-Object FullName
)

if ($MMProjFiles.Count -eq 1) {
    # 同資料夾只有一個 mmproj，直接使用
    $MMProj = $MMProjFiles[0]
}
elseif ($MMProjFiles.Count -gt 1) {
    # 移除模型檔名最後的量化標記，用來配對 mmproj
    $ModelBase = $Alias

    $ModelBase = $ModelBase -replace `
        "(?i)[._-](Q\d+(_[A-Z0-9]+)*|IQ\d+(_[A-Z0-9]+)*|F16|BF16|FP16|MXFP4)$", `
        ""

    foreach ($File in $MMProjFiles) {
        if (
            $File.Name.IndexOf(
                $ModelBase,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        ) {
            $MMProj = $File
            break
        }
    }
}

$ExtraArgs = @()

if ($null -ne $MMProj) {
    $ExtraArgs += @(
        "--mmproj"
        $MMProj.FullName
    )
}

# ============================================================
# 顯示啟動設定
# ============================================================

Write-Host ""
Write-Host "主模型：$ModelFilename"

if ($null -ne $MMProj) {
    Write-Host "圖片模型：$($MMProj.Name)"
    Write-Host "模式：文字＋圖片"
}
else {
    Write-Host "圖片模型：未找到"
    Write-Host "模式：純文字"
}

$SlotContext = [math]::Floor($ContextSize / $Parallel)

Write-Host ""
Write-Host "API 模型名稱：$Alias"
Write-Host "總 Context：$ContextSize"
Write-Host "平行請求數：$Parallel"
Write-Host "每個 Slot 約可用：$SlotContext tokens"
Write-Host ""
Write-Host "網頁：http://${HostAddress}:$Port"
Write-Host "API Base URL：http://${HostAddress}:$Port/v1"
Write-Host ""
Write-Host "停止伺服器請按 Ctrl+C"
Write-Host ""

# ============================================================
# 組合 llama-server 參數
# ============================================================

$ServerArgs = @(
    "--model"
    $Model.FullName

    "--alias"
    $Alias

    "--host"
    $HostAddress

    "--port"
    "$Port"

    "--ctx-size"
    "$ContextSize"

    "--parallel"
    "$Parallel"

    "--batch-size"
    "$BatchSize"

    "--ubatch-size"
    "$UBatchSize"

    "--cache-type-k"
    "q8_0"

    "--cache-type-v"
    "q8_0"

    "--flash-attn"
    "auto"

    "--n-predict"
    "1024"
)

if ($ExtraArgs.Count -gt 0) {
    $ServerArgs += $ExtraArgs
}

# ============================================================
# 啟動 llama-server
# ============================================================

try {
    $ServerProcess = Start-Process `
        -FilePath $Server `
        -ArgumentList $ServerArgs `
        -WorkingDirectory $ScriptDir `
        -NoNewWindow `
        -PassThru

    $script:ServerProcess = $ServerProcess
}
catch {
    Write-Host "無法啟動 llama-server。" -ForegroundColor Red
    Write-Host $_.Exception.Message

    Pause-AndExit 1
}

# ============================================================
# 等待啟動完成
# ============================================================

$Ready = $false
$HealthUrl = "http://${HostAddress}:$Port/health"

for ($i = 1; $i -le 240; $i++) {
    try {
        $Response = Invoke-WebRequest `
            -Uri $HealthUrl `
            -UseBasicParsing `
            -TimeoutSec 2 `
            -ErrorAction Stop

        if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300) {
            $Ready = $true
            break
        }
    }
    catch {
        # 模型尚未載入完成，繼續等待
    }

    $ServerProcess.Refresh()

    if ($ServerProcess.HasExited) {
        Write-Host ""
        Write-Host "llama-server 啟動失敗。" -ForegroundColor Red
        Write-Host "結束代碼：$($ServerProcess.ExitCode)"

        Pause-AndExit 1
    }

    Start-Sleep -Seconds 1
}

if (-not $Ready) {
    Write-Host ""
    Write-Host "等待模型啟動逾時。" -ForegroundColor Red

    Stop-LlamaServer
    Pause-AndExit 1
}

# ============================================================
# 啟動成功
# ============================================================

Write-Host ""
Write-Host "========================================"
Write-Host "llama-server 已成功啟動" -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Write-Host "網頁：http://${HostAddress}:$Port"
Write-Host "API：http://${HostAddress}:$Port/v1"
Write-Host "模型：$Alias"
Write-Host ""
Write-Host "健康檢查："
Write-Host "curl.exe http://${HostAddress}:$Port/health"
Write-Host ""
Write-Host "模型清單："
Write-Host "curl.exe http://${HostAddress}:$Port/v1/models"
Write-Host ""
Write-Host "伺服器正在執行，按 Ctrl+C 停止。"
Write-Host ""

# 自動開啟 llama.cpp 網頁
try {
    Start-Process "http://${HostAddress}:$Port"
}
catch {
    # 無法開啟瀏覽器不影響伺服器
}

# ============================================================
# 持續監控伺服器
# ============================================================

try {
    while (-not $ServerProcess.HasExited) {
        Start-Sleep -Seconds 1
        $ServerProcess.Refresh()
    }

    Write-Host ""
    Write-Host "llama-server 已停止。"

    if ($ServerProcess.ExitCode -ne 0) {
        Write-Host "結束代碼：$($ServerProcess.ExitCode)" -ForegroundColor Yellow
    }
}
finally {
    Stop-LlamaServer
}

Write-Host ""
Read-Host "按 Enter 關閉"