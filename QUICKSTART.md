# 简单使用教程

如果你觉得下面这些命令太复杂，直接看这个文件：

[中文傻瓜版说明.md](中文傻瓜版说明.md)

你现在可以用双击脚本：

```text
1_编辑API配置.command
2_检查真实交易配置.command
3_打开真实交易控制台.command
4_紧急停止.command
5_解除紧急停止.command
6_停止控制台.command
7_打开5U真实试用控制台.command
```

可以先接真实交易所 API，但暂时不存钱。没 USDT 的时候，真实买单不会成交。

下面是给以后调试用的命令版说明。

## 1. 安装

```bash
cd ~/Downloads/vibe-trading-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev,ai]"
```

如果你的 pip 源遇到 SSL 证书错误，可以临时改用：

```bash
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  -i https://pypi.org/simple -e ".[dev,ai]"
```

以后每次使用前，如果终端没进虚拟环境，先执行：

```bash
cd ~/Downloads/vibe-trading-bot
source .venv/bin/activate
```

## 2. 跑本地模拟盘

```bash
vibe-trader init-db
vibe-trader run-once
```

成功后会生成：

```text
reports/obsidian/account_dashboard.md
reports/obsidian/daily/YYYY-MM-DD.md
data/vibe_trader.sqlite3
```

直接打开 Obsidian 看板：

```bash
open reports/obsidian/account_dashboard.md
```

你会看到：

- 账户概览
- 当前持仓
- 今日盈亏
- 风控指标
- 今日操作
- 最近信号
- 风控事件
- 今日复盘
- 绩效摘要：胜率、已实现盈亏、profit factor、回撤

## 3. 打开网页 dashboard

```bash
vibe-trader dashboard
```

Streamlit 会在浏览器打开一个控制台页面，可以展示资产曲线、持仓、订单、信号、风控状态和复盘，也可以执行经过风控检查的操作。
现在 dashboard 也是控制台，可以执行：

- Run Once：跑一轮策略和风控，满足条件会下单。
- Pause / Resume：暂停或恢复交易。
- Kill Switch：紧急停止，开启后任何交易动作都会被挡住。
- Clear Kill Switch：解除紧急停止。
- Submit Manual Order：提交一笔风控检查后的手动市价单。

live 模式下，手动订单还必须输入：

```text
EXECUTE_REAL_ORDER
```

## 4. 跑一个简单回测

```bash
vibe-trader backtest
open reports/backtest_summary.md
```

这个回测只是工程 smoke test：它会复用同一套规则策略，并计入配置里的手续费和滑点，但不能证明策略有稳定收益。

也可以直接看最近交易绩效：

```bash
vibe-trader performance
```

它会输出已成交订单、已平仓交易、胜率、已实现盈亏、手续费、profit factor、收益率、最大回撤和当前回撤。

## 5. 每 15 分钟自动跑

```bash
vibe-trader schedule
```

默认每 15 分钟跑一次。先建议你用这个本地模式跑几天，观察看板、信号、拒单原因和日志是否符合直觉。

## 6. 切到 Binance Spot Testnet sandbox

先复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`，填入 Binance Spot Testnet 的 key：

```text
VIBE_TRADER_MODE=sandbox
BINANCE_API_KEY=你的testnet_key
BINANCE_SECRET=你的testnet_secret
```

注意：

- 必须是 testnet key，不要用生产 key。
- 禁止提现权限。
- 如果本地状态和交易所状态不一致，机器人会拒绝交易。

检查配置：

```bash
vibe-trader --config configs/sandbox_binance.yaml doctor
```

运行一轮：

```bash
vibe-trader --config configs/sandbox_binance.yaml run-once
```

也可以在 sandbox 下手动买 10 USDT 的 BTC：

```bash
vibe-trader --config configs/sandbox_binance.yaml manual-order \
  --symbol BTC/USDT --side buy --quote-qty 10
```

## 7. 小资金 live 现货模式

先强调：这会使用真实资金。只建议现货、小金额、无杠杆、无提现权限 API key。

`.env` 至少要有：

```text
VIBE_TRADER_MODE=live
BINANCE_API_KEY=你的生产现货key
BINANCE_SECRET=你的生产现货secret
LIVE_TRADING_ACK=true
LIVE_TRADING_CONFIRM_TEXT=I_UNDERSTAND_REAL_MONEY_RISK
MAX_LIVE_EQUITY=50
```

检查 live 门槛：

```bash
vibe-trader --config configs/live_binance_spot_small.yaml doctor
```

手动小额买入示例：

```bash
vibe-trader --config configs/live_binance_spot_small.yaml manual-order \
  --symbol BTC/USDT --side buy --quote-qty 10 --confirm EXECUTE_REAL_ORDER
```

策略自动跑一轮：

```bash
vibe-trader --config configs/live_binance_spot_small.yaml run-once
```

紧急停止：

```bash
vibe-trader --config configs/live_binance_spot_small.yaml kill-switch
```

## 6. 常用文件

```text
configs/default.yaml              # 本地 paper demo
configs/sandbox_binance.yaml      # Binance Spot Testnet
configs/live_binance_spot_small.yaml # 小资金现货 live
.env.example                      # 环境变量模板
data/*.sqlite3                    # 本地数据库，不提交 GitHub
reports/obsidian/*.md             # Obsidian 看板
docs/live_trading_gate.md         # 实盘前门槛
docs/risk_policy.md               # 风控说明
```

## 7. 实盘前不要做什么

- 不要把 `.env` 提交到 GitHub。
- 不要开提现权限。
- 不要在没有 `doctor` 通过时使用 live。
- 不要让 LLM 自动修改实盘参数。
- 不要因为一次 sandbox 盈利就小资金实盘。
- 不要开杠杆、合约、提现权限。

## 8. 跑测试

```bash
pytest
```

如果测试不通过，先不要继续接 sandbox，更不要考虑实盘。
