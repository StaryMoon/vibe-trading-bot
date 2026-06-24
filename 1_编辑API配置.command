#!/bin/zsh
set -e
cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

open -a TextEdit .env
echo "已打开 .env。请填 BINANCE_API_KEY / BINANCE_SECRET。"
echo "填完保存即可，然后双击 2_检查真实交易配置.command。"
read -k 1 "?按任意键关闭这个窗口..."
