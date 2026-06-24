#!/bin/zsh
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

vibe-trader --config configs/live_binance_spot_small.yaml kill-switch
echo "已开启紧急停止。任何交易动作都会被拦截。"
read -k 1 "?按任意键关闭这个窗口..."
