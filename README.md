# npm-safe

`npm install` の前に危険パッケージを自動検出してブロックするラッパー。

## なぜ必要か

2026年3月、正規の `axios` パッケージ（v1.14.1, v0.30.4）にRAT（リモートアクセストロイの木馬）が仕込まれた。`npm install` した瞬間にマルウェアが実行され、ペイロード実行後に自己消去する。

このツールは `npm install` コマンドをラップして、実行前に `package.json` と `package-lock.json` をチェックし、危険パッケージが含まれていたらインストールを中止する。

## 特徴

- **ライブラリ依存ゼロ** — bash + Python 標準ライブラリのみ
- **直接依存も間接依存も検出** — package-lock.json をJSONパースして全依存をチェック
- **正確な判定** — テキスト検索ではなくJSON構造を解析。誤検出しない
- **bash / PowerShell 両対応**

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

## インストール

```bash
# ファイルを配置
mkdir -p ~/bin
cp npm-safe.sh ~/bin/
cp npm-safe-check.py ~/bin/
chmod +x ~/bin/npm-safe.sh

# bash に alias 追加
echo 'alias npm="bash ~/bin/npm-safe.sh"' >> ~/.bashrc
source ~/.bashrc
```

### PowerShell

```powershell
# ファイルを配置
Copy-Item npm-safe.ps1 $HOME\bin\

# PowerShell プロファイルに alias 追加
Add-Content $PROFILE 'Set-Alias npm C:\Users\$env:USERNAME\bin\npm-safe.ps1'
```

## 使い方

普通に `npm install` するだけ。ラッパーが自動的にチェックする。

```bash
$ npm install
[npm-safe] 危険パッケージチェック中...
✓ 危険パッケージなし。npm install を実行します。
```

危険パッケージが見つかった場合:

```bash
$ npm install
[npm-safe] 危険パッケージチェック中...

⚠ [package.json] axios@1.14.1 (RATが仕込まれたバージョン)

npm install を中止しました。
上記のパッケージを修正してから再実行してください。
```

## ファイル構成

| ファイル | 説明 |
|---------|------|
| `npm-safe.sh` | bash ラッパー。`npm` コマンドをフックして、install 前にチェックを実行 |
| `npm-safe-check.py` | チェッカー本体。package.json / package-lock.json をJSONパースして危険パッケージを検出 |
| `npm-safe.ps1` | PowerShell 版ラッパー（Windows ネイティブ用） |

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
