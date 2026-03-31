# npm のセキュリティラッパー（PowerShell版）
# 使い方: Set-Alias npm C:\Users\tatut\bin\npm-safe.ps1 を $PROFILE に追加

$BlockedAll = @(
    "axois", "axi0s", "solana-transaction-toolkit", "solana-stable-web-huks",
    "crypto-encrypt-ts", "lottie-plyer", "loadsh", "expres", "reactjs-core",
    "node-hide-console-windows", "eslint-plugin-prettier-format",
    "prettier-plugin-xml2", "jest-cov-reporter", "event-handle-package",
    "yolowide", "icloud-cod", "warbeast2000", "kodaborat", "bb-templates"
)

$BlockedExact = @(
    @{Name="axios"; Version="1.14.1"},
    @{Name="axios"; Version="0.30.4"},
    @{Name="@solana/web3.js"; Version="1.95.6"},
    @{Name="@solana/web3.js"; Version="1.95.7"},
    @{Name="@lottiefiles/lottie-player"; Version="2.0.8"}
)

function Test-DangerousPackages {
    param([string]$FilePath)
    if (-not (Test-Path $FilePath)) { return $false }
    $content = Get-Content $FilePath -Raw
    $found = $false

    foreach ($pkg in $BlockedAll) {
        if ($content -match [regex]::Escape("`"$pkg`"")) {
            Write-Host "!!! 危険: $FilePath に悪意のあるパッケージ '$pkg' が含まれています！" -ForegroundColor Red
            $found = $true
        }
    }
    foreach ($entry in $BlockedExact) {
        if ($content -match [regex]::Escape("`"$($entry.Name)`"") -and $content -match [regex]::Escape("`"$($entry.Version)`"")) {
            Write-Host "!!! 危険: $FilePath に $($entry.Name)@$($entry.Version) が含まれている可能性があります！" -ForegroundColor Red
            $found = $true
        }
    }
    return $found
}

if ($args[0] -in @("install", "i", "add", "ci")) {
    Write-Host "[npm-safe] 危険パッケージチェック中..." -ForegroundColor Yellow
    $blocked = $false
    $blocked = (Test-DangerousPackages "package.json") -or $blocked
    $blocked = (Test-DangerousPackages "package-lock.json") -or $blocked

    if ($blocked) {
        Write-Host "`nnpm install を中止しました。" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK 危険パッケージなし。" -ForegroundColor Green
}

& npm.cmd @args
