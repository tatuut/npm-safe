#!/bin/bash
# safe.sh — npm/pnpm/bun/yarn 共通セキュリティラッパー
# install 実行前に危険パッケージをチェックする。
#
# 使い方: alias npm='~/bin/safe.sh npm'
#         alias pnpm='~/bin/safe.sh pnpm'
#         alias bun='~/bin/safe.sh bun'
#         alias yarn='~/bin/safe.sh yarn'

PM="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
  install|i|add|ci)
    python "$SCRIPT_DIR/npm-safe-check.py" --full "$PM" "$@"
    if [ $? -ne 0 ]; then exit 1; fi
    ;;
esac

command "$PM" "$@"
