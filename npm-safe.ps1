# npm のセキュリティラッパー（PowerShell版）
# 使い方: Set-Alias npm C:\Users\$env:USERNAME\bin\npm-safe.ps1 を $PROFILE に追加

$CheckScript = Join-Path $PSScriptRoot "npm-safe-check.py"

function Show-Results($output) {
    Write-Host ""
    foreach ($line in $output -split "`n") {
        if ($line -match "^DANGER: (.+)$") {
            Write-Host "  ⚠ $($Matches[1])" -ForegroundColor Red
        } elseif ($line -match "^WARN: (.+)$") {
            Write-Host "  ⚠ $($Matches[1])" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

function Confirm-Warn($output) {
    if ($output -match "^WARN:") {
        Show-Results $output
        $answer = Read-Host "未確認バージョンが含まれています。インストールしますか？ [y/N]"
        if ($answer -ne "y" -and $answer -ne "Y") {
            Write-Host "npm install を中止しました。" -ForegroundColor Red
            exit 1
        }
    }
}

if ($args[0] -in @("install", "i", "add", "ci")) {
    $subcmd = $args[0]
    Write-Host "[npm-safe] 危険パッケージチェック中..." -ForegroundColor Yellow

    # --- Step 1: CLI引数のパッケージ名をチェック ---
    $pkgArgs = @()
    $skipFlags = @("--registry", "--cache", "--prefix", "--tag")
    $skipNext = $false
    foreach ($arg in $args[1..($args.Length - 1)]) {
        if ($skipNext) { $skipNext = $false; continue }
        if ($arg -in $skipFlags) { $skipNext = $true; continue }
        if ($arg -match "^-") { continue }
        $pkgArgs += $arg
    }

    if ($pkgArgs.Count -gt 0) {
        $result = & python $CheckScript --check-args @pkgArgs 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Show-Results $result
            Write-Host "npm $subcmd を中止しました。" -ForegroundColor Red
            exit 1
        }
        Confirm-Warn $result
    }

    # --- Step 2: 既存の package.json チェック ---
    $result = & python $CheckScript 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Show-Results $result
        Write-Host "npm $subcmd を中止しました。" -ForegroundColor Red
        exit 1
    }
    Confirm-Warn $result

    # --- Step 3: 推移的依存チェック（ci 以外） ---
    if ($subcmd -ne "ci") {
        $lockBackup = $null
        if (Test-Path "package-lock.json") {
            $lockBackup = [System.IO.Path]::GetTempFileName()
            Copy-Item "package-lock.json" $lockBackup
        }

        Write-Host "[npm-safe] 推移的依存を解決中（--package-lock-only）..." -ForegroundColor Yellow
        & npm.cmd install --package-lock-only @($args[1..($args.Length - 1)]) 2>$null

        $result = & python $CheckScript 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Show-Results $result
            if ($lockBackup) {
                Copy-Item $lockBackup "package-lock.json"
                Remove-Item $lockBackup
            } elseif (Test-Path "package-lock.json") {
                Remove-Item "package-lock.json"
            }
            Write-Host "npm $subcmd を中止しました（推移的依存に危険パッケージ検出）。" -ForegroundColor Red
            exit 1
        }

        Confirm-Warn $result
        if ($lockBackup) { Remove-Item $lockBackup }
    }

    Write-Host "✓ 危険パッケージなし。npm $subcmd を実行します。" -ForegroundColor Green
}

& npm.cmd @args
