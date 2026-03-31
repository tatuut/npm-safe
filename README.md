# npm-safe

`npm install` / `pnpm install` の前に危険パッケージを自動検出してブロックするラッパー。

## なぜ必要か

2026年3月、正規の `axios` パッケージ（v1.14.1, v0.30.4）にRAT（リモートアクセストロイの木馬）が仕込まれた。`npm install` した瞬間にマルウェアが実行され、ペイロード実行後に自己消去する。

このツールは `npm install` / `pnpm install` コマンドをラップして、実行前にチェックし、危険パッケージが含まれていたらインストールを中止する。

## 何をチェックするか

3段階でチェックする。**推移的依存（間接依存）も検出する。**

### Step 1: CLI引数チェック

`npm install axois` のようにコマンドで直接指定されたパッケージ名をブロックリストと照合する。危険パッケージなら即座に中止。

### Step 2: 既存依存チェック

- **package.json** — 直接依存に危険パッケージがないか
- **package-lock.json** — 間接依存も含めてJSONパースで正確に判定
- **pnpm-lock.yaml** — pnpm の間接依存もチェック
- **node_modules** — インストール済みパッケージを `npm list --all --json` で一括チェック

### Step 3: 推移的依存チェック

`npm install --package-lock-only`（pnpm は `--lockfile-only`）を実行してロックファイルだけを更新する。**node_modules には触れないのでマルウェアは実行されない。** 更新されたロックファイルをチェックし、危険な推移的依存が見つかればロックファイルを復元して中止する。

## 前提条件

- **bash** (Git Bash, WSL, macOS/Linux 標準) または **PowerShell**
- **Python 3.8+**
- **npm** (v7+) または **pnpm**

サードパーティパッケージのインストールは不要。Python 標準ライブラリのみ使用。

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

ロックファイルのチェックはJSONパースのみで、体感ゼロ。
`--package-lock-only` による推移的依存の解決が追加コスト。

### 実測値

| チェック | 処理内容 | 実測値 |
|---------|---------|--------|
| package.json | JSONパース + dict lookup | **< 1ms** |
| package-lock.json (1,500パッケージ) | JSONパース + 全パッケージ走査 | **~5ms** |
| pnpm-lock.yaml | テキスト全体に正規表現 | **~10ms** |
| `--package-lock-only` | ロックファイルだけ更新（推移的依存解決） | **~2-8秒** |
| node_modules (`npm list --all --json`) | サブプロセス1回 + JSONツリー走査 | **~1-6秒** |

- `npm install` 前（node_modules なし）: ロックファイルチェック **~15ms** + 推移的依存解決 **~2-8秒**
- 既存プロジェクト（node_modules あり）: 上記 + node_modules チェック **~1-6秒**

## インストール

```bash
# ファイルを配置
mkdir -p ~/bin
cp npm-safe.sh pnpm-safe.sh npm-safe-check.py ~/bin/
chmod +x ~/bin/npm-safe.sh ~/bin/pnpm-safe.sh

# bash に alias 追加
echo 'alias npm="bash ~/bin/npm-safe.sh"' >> ~/.bashrc
echo 'alias pnpm="bash ~/bin/pnpm-safe.sh"' >> ~/.bashrc
source ~/.bashrc
```

### PowerShell

```powershell
Copy-Item npm-safe.ps1, npm-safe-check.py $HOME\bin\
Add-Content $PROFILE 'Set-Alias npm C:\Users\$env:USERNAME\bin\npm-safe.ps1'
```

## 使い方

普通に `npm install` / `pnpm install` するだけ。

```bash
$ npm install
[npm-safe] 危険パッケージチェック中...
[npm-safe] 推移的依存を解決中（--package-lock-only）...
✓ 危険パッケージなし。npm install を実行します。
```

危険パッケージが見つかった場合:

```bash
$ npm install axois
[npm-safe] 危険パッケージチェック中...

⚠ [引数] axois@* (全バージョン危険)

npm install を中止しました。
上記のパッケージを修正してから再実行してください。
```

推移的依存で検出された場合:

```bash
$ npm install
[npm-safe] 危険パッケージチェック中...
[npm-safe] 推移的依存を解決中（--package-lock-only）...

⚠ [package-lock.json] axios@1.14.1 (危険バージョン)

npm install を中止しました（推移的依存に危険パッケージ検出）。
上記のパッケージを修正してから再実行してください。
```

## ファイル構成

| ファイル | 説明 |
|---------|------|
| `npm-safe.sh` | bash ラッパー（npm 用）。3段階チェック後に `npm install` を実行 |
| `pnpm-safe.sh` | bash ラッパー（pnpm 用）。3段階チェック後に `pnpm install` を実行 |
| `npm-safe-check.py` | チェッカー本体。npm / pnpm 両方のロックファイルに対応 |
| `npm-safe.ps1` | PowerShell 版ラッパー |

## 危険パッケージの追加

`npm-safe-check.py` の先頭にある `BLOCKED_EXACT` と `BLOCKED_ALL` を編集する:

```python
# 特定バージョンが危険（正規パッケージの侵害版）
BLOCKED_EXACT = {
    "axios": {"1.14.1", "0.30.4"},
    "new-package": {"3.2.1"},  # 追加
}

# 全バージョンが危険（タイポスクワッティング）
BLOCKED_ALL = {
    "axois", "axi0s",
    "new-typosquat",  # 追加
}
```

## 参考

- [Socket.dev Blog](https://socket.dev/blog) — サプライチェーン攻撃の最新情報
- [GitHub Advisory Database](https://github.com/advisories) — 脆弱性データベース
- [Phylum Blog](https://blog.phylum.io) — マルウェアパッケージの分析レポート

## License

MIT
