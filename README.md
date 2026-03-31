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

## 3段階判定

| 判定 | 条件 | 動作 |
|------|------|------|
| **DANGER** | `dangerous` リストに一致 / タイポスクワッティング | **インストール中止** |
| **OK** | `safe` リストに一致 / vuls.json に未登録のパッケージ | サイレント通過 |
| **未確認** | vuls.json に登録済みだが `safe` にも `dangerous` にもないバージョン | **対話プロンプト**（下記参照） |

`safe` に登録されたバージョンを使えば安全が確認済み。新しいバージョンが出たら、確認後に `safe` リストに追加していくことでバージョンを一つずつ固定できる。推移的依存にも同じ判定が適用される。

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

- **[a]** — 全ての未確認バージョンをインストール
- **[n]** — 全て中止（デフォルト）
- **[o]** — 一つずつ確認して y/N で選択

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
cp npm-safe.sh pnpm-safe.sh npm-safe-check.py vuls.json ~/bin/
chmod +x ~/bin/npm-safe.sh ~/bin/pnpm-safe.sh

# bash に alias 追加
echo 'alias npm="bash ~/bin/npm-safe.sh"' >> ~/.bashrc
echo 'alias pnpm="bash ~/bin/pnpm-safe.sh"' >> ~/.bashrc
source ~/.bashrc
```

### PowerShell

```powershell
Copy-Item npm-safe.ps1, npm-safe-check.py, vuls.json $HOME\bin\
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

未確認バージョンが見つかった場合（対話プロンプト）:

```bash
$ npm install axios@1.15.0
[npm-safe] 危険パッケージチェック中...

未確認バージョンが見つかりました:
  1. [引数] axios@1.15.0 (安全確認済み: 0.30.2, 0.30.3, 1.12.2, 1.13.0, 1.13.1, 1.14.0)

どうしますか？
  [a] 全てインストール
  [n] 全て中止
  [o] 一つずつ確認
選択 [a/n/o]: n
中止しました。
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
| `vuls.json` | 危険パッケージ定義。Pythonコードを触らずに追加・削除できる |

## 危険パッケージの追加

`vuls.json` を編集する（Pythonコードの変更は不要）:

```jsonc
{
  "exact": {
    "axios": {
      "dangerous": ["1.14.1", "0.30.4"],     // 危険バージョン → DANGER
      "safe": ["1.14.0", "1.13.0", "0.30.3"], // 安全確認済み → OK
      "type": "RAT",                           // それ以外 → WARN
      "added": "2026-03-31",
      "source": "https://..."
    },
    "new-package": {                    // ← 追加
      "dangerous": ["3.2.1"],
      "safe": ["3.2.0", "3.1.0"],
      "type": "バックドア",
      "added": "2026-04-01"
    }
  },
  "all": {
    "axois": { "impersonates": "axios", "type": "情報窃取", "added": "2026-03-31" },
    "new-typosquat": { "type": "マルウェア", "added": "2026-04-01" }  // ← 追加
  }
}
```

新しい安全バージョンを確認したら `safe` リストに追加するだけ。`dangerous` と `safe` のどちらにもないバージョンは自動的に警告対象になる。

## 参考

- [Socket.dev Blog](https://socket.dev/blog) — サプライチェーン攻撃の最新情報
- [GitHub Advisory Database](https://github.com/advisories) — 脆弱性データベース
- [Phylum Blog](https://blog.phylum.io) — マルウェアパッケージの分析レポート

## License

MIT
