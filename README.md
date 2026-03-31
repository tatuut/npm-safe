# npm-safe

`npm install` / `pnpm install` / `bun install` / `yarn install` の前に危険パッケージを自動検出してブロックするラッパー。

## なぜ必要か

2026年3月、正規の `axios` パッケージ（v1.14.1, v0.30.4）にRAT（リモートアクセストロイの木馬）が仕込まれた。`npm install` した瞬間にマルウェアが実行され、ペイロード実行後に自己消去する。

このツールは install コマンドをラップして、実行前にチェックし、危険パッケージが含まれていたらインストールを中止する。

## 対応パッケージマネージャー

| PM | ロックファイル | 推移的依存チェック |
|----|-------------|----------------|
| **npm** | package-lock.json | ✓ `--package-lock-only` |
| **pnpm** | pnpm-lock.yaml | ✓ `--lockfile-only` |
| **bun** | bun.lock (JSONC, Bun 1.2+) | ✓ `--lockfile-only` |
| **yarn** (Berry v2+) | yarn.lock | ✓ `--mode update-lockfile` |
| **yarn** (Classic v1) | yarn.lock | ✗（既存lockfileのみ） |

> yarn v1 はlockfile-onlyモードがないため、推移的依存の事前チェックはスキップされる。既存のyarn.lockはチェックされる。

## 何をチェックするか

3段階でチェックする。**推移的依存（間接依存）も検出する。**

### Step 1: CLI引数チェック

`npm install axois` のようにコマンドで直接指定されたパッケージ名をブロックリストと照合する。危険パッケージなら即座に中止。

### Step 2: 既存依存チェック

- **package.json** — 直接依存に危険パッケージがないか
- **ロックファイル** — 間接依存も含めてチェック（PM に応じたパーサーで正確に解析）

### Step 3: 推移的依存チェック

ロックファイルだけを更新して（`--package-lock-only` 等）推移的依存を解決する。**node_modules には触れないのでマルウェアは実行されない。** 更新されたロックファイルをチェックし、危険な推移的依存が見つかればロックファイルを復元して中止する。

## 3段階判定

| 判定 | 条件 | 動作 |
|------|------|------|
| **DANGER** | `dangerous` リストに一致 / タイポスクワッティング | **インストール中止** |
| **OK** | `safe` リストに一致 / vuls.json に未登録のパッケージ | サイレント通過 |
| **未確認** | vuls.json に登録済みだが `safe` にも `dangerous` にもないバージョン | **対話プロンプト** |

### 未確認バージョンの対話プロンプト

未確認バージョンが見つかると、ユーザーに選択を求める:

```
未確認バージョンが見つかりました:
  1. axios@1.15.0 (安全確認済み: 0.30.2, 0.30.3, 1.12.2, 1.13.0, 1.13.1, 1.14.0)

どうしますか？
  [a] 全てインストール
  [n] 全て中止
  [o] 一つずつ確認
選択 [a/n/o]:
```

## 前提条件

- **bash** (Git Bash, WSL, macOS/Linux) または **PowerShell**
- **Python 3.8+**
- **npm** / **pnpm** / **bun** / **yarn** のいずれか

サードパーティパッケージのインストールは不要。Python 標準ライブラリのみ使用。

## アーキテクチャ

```
safe.sh / safe.ps1       ← 薄いエントリポイント（全PM共通、~20行）
  └→ npm-safe-check.py   ← チェック・対話・推移的依存解決を全て処理
       └→ vuls.json       ← 危険パッケージ定義（コード変更不要で追加可能）
```

ロジック変更は **npm-safe-check.py の1ファイルだけ**。シェルラッパーは PM 名を渡すだけ。

## ブロック対象

### 正規パッケージの侵害版（特定バージョンのみ危険）

| パッケージ | 危険バージョン | 安全バージョン | 種別 |
|-----------|-------------|-------------|------|
| axios | 1.14.1, 0.30.4 | 1.14.0, 0.30.3 | RAT |
| @solana/web3.js | 1.95.6, 1.95.7 | 1.95.8+ | 秘密鍵窃取 |
| @lottiefiles/lottie-player | 2.0.8 | 2.0.9+ | Web3ウォレット窃取 |

### タイポスクワッティング（全バージョン危険）

| パッケージ | 偽装先 | 種別 |
|-----------|--------|------|
| axois | axios | 情報窃取 |
| axi0s | axios | マルウェア |
| loadsh | lodash | 情報窃取 |
| expres | express | バックドア |
| reactjs-core | react | 情報窃取 |
| lottie-plyer | lottie-player | ウォレット窃取 |
| solana-transaction-toolkit | — | ウォレット窃取 |
| solana-stable-web-huks | — | ウォレット窃取 |
| crypto-encrypt-ts | CryptoJS | 情報窃取+マイナー |
| node-hide-console-windows | node-hide-console-window | RAT+マイナー |
| eslint-plugin-prettier-format | ESLintプラグイン | 情報窃取 |
| prettier-plugin-xml2 | prettierプラグイン | マルウェア |
| jest-cov-reporter | Jestカバレッジ | 情報窃取 |
| event-handle-package | — | RAT（北朝鮮系） |
| yolowide | — | 情報窃取（北朝鮮系） |
| icloud-cod | — | スパイウェア |
| warbeast2000 | — | SSH鍵窃取 |
| kodaborat | — | SSH鍵窃取 |
| bb-templates | — | 情報窃取 |

## 速度

| チェック | 処理内容 | 実測値 |
|---------|---------|--------|
| package.json | JSONパース + dict lookup | **< 1ms** |
| package-lock.json (1,500パッケージ) | JSONパース + 全パッケージ走査 | **~5ms** |
| pnpm-lock.yaml | テキスト全体に正規表現 | **~10ms** |
| bun.lock | JSONC パース + packages 走査 | **~5ms** |
| yarn.lock | テキスト行単位解析 | **~10ms** |
| 推移的依存解決 | ロックファイルだけ更新 | **~2-8秒** |

## インストール

### bash（推奨）

```bash
mkdir -p ~/bin
cp safe.sh npm-safe-check.py vuls.json ~/bin/
chmod +x ~/bin/safe.sh

# .bashrc に追加
cat >> ~/.bashrc << 'EOF'
alias npm='~/bin/safe.sh npm'
alias pnpm='~/bin/safe.sh pnpm'
alias bun='~/bin/safe.sh bun'
alias yarn='~/bin/safe.sh yarn'
EOF
source ~/.bashrc
```

### PowerShell

```powershell
Copy-Item safe.ps1, npm-safe-check.py, vuls.json $HOME\bin\

# $PROFILE に追加
Add-Content $PROFILE @'
function npm  { & $HOME\bin\safe.ps1 npm  @args }
function pnpm { & $HOME\bin\safe.ps1 pnpm @args }
function bun  { & $HOME\bin\safe.ps1 bun  @args }
function yarn { & $HOME\bin\safe.ps1 yarn @args }
'@
```

## 使い方

普通に `npm install` / `pnpm install` / `bun install` / `yarn install` するだけ。

```bash
$ npm install
[npm-safe] 危険パッケージチェック中...
[npm-safe] 推移的依存を解決中...
✓ 危険パッケージなし。npm install を実行します。
```

危険パッケージが見つかった場合:

```bash
$ bun install axois
[bun-safe] 危険パッケージチェック中...

  ⚠ [引数] axois@* (全バージョン危険)

bun install を中止しました。
上記のパッケージを修正してから再実行してください。
```

## ファイル構成

| ファイル | 説明 |
|---------|------|
| `safe.sh` | bash ラッパー（全PM共通）。alias で各 PM にバインド |
| `safe.ps1` | PowerShell ラッパー（全PM共通） |
| `npm-safe-check.py` | チェッカー本体。全PM のロックファイル解析・対話・推移的依存解決 |
| `vuls.json` | 危険パッケージ定義。Python コードを触らずに追加・削除できる |

## 危険パッケージの追加

`vuls.json` を編集する（Python コードの変更は不要）:

```jsonc
{
  "exact": {
    "new-package": {
      "dangerous": ["3.2.1"],
      "safe": ["3.2.0", "3.1.0"],
      "type": "バックドア",
      "added": "2026-04-01"
    }
  },
  "all": {
    "new-typosquat": { "type": "マルウェア", "added": "2026-04-01" }
  }
}
```

## テスト

```bash
python test_check.py
```

43 テスト: CLI引数、package.json、package-lock.json、pnpm-lock.yaml、bun.lock (JSONC)、yarn.lock (v1/v2)、空ディレクトリ。

## 参考

- [Socket.dev Blog](https://socket.dev/blog) — サプライチェーン攻撃の最新情報
- [GitHub Advisory Database](https://github.com/advisories) — 脆弱性データベース
- [Phylum Blog](https://blog.phylum.io) — マルウェアパッケージの分析レポート

## License

MIT
