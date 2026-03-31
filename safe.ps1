# safe.ps1 — npm/pnpm/bun/yarn 共通セキュリティラッパー
# install 実行前に危険パッケージをチェックする。
#
# 使い方（$PROFILE に追加）:
#   function npm  { & C:\Users\$env:USERNAME\bin\safe.ps1 npm  @args }
#   function pnpm { & C:\Users\$env:USERNAME\bin\safe.ps1 pnpm @args }
#   function bun  { & C:\Users\$env:USERNAME\bin\safe.ps1 bun  @args }
#   function yarn { & C:\Users\$env:USERNAME\bin\safe.ps1 yarn @args }

$PM = $args[0]
$PMArgs = @()
if ($args.Length -gt 1) {
    $PMArgs = $args[1..($args.Length - 1)]
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($PMArgs.Count -gt 0 -and $PMArgs[0] -in @("install", "i", "add", "ci")) {
    & python "$ScriptDir\npm-safe-check.py" --full $PM @PMArgs
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# 元のコマンドを実行（PowerShell 関数による再帰を回避）
$exe = (Get-Command $PM -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1).Source
if (-not $exe) {
    Write-Host "ERROR: $PM が見つかりません" -ForegroundColor Red
    exit 1
}
& $exe @PMArgs
