#!/bin/zsh
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

vibe-trader --config configs/live_binance_spot_small.yaml clear-kill-switch
echo "已解除紧急停止。请确认配置无误后再操作。"
read -k 1 "?按任意键关闭这个窗口..."
