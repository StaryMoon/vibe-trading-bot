from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from vibe_trader.analysis.performance import summarize_performance
from vibe_trader.app import TradingApp
from vibe_trader.config.loader import load_config
from vibe_trader.data.repository import SQLiteRepository


def _config_arg() -> str:
    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return "configs/default.yaml"


cfg = load_config(_config_arg())
repo = SQLiteRepository(cfg)
repo.init_db()
control = repo.get_control()

st.set_page_config(page_title="量化交易机器人", layout="wide")
st.title("量化交易机器人")
mode_label = {"paper": "模拟盘", "sandbox": "交易所测试网", "live": "真实小资金实盘"}.get(
    cfg.trading_mode, cfg.trading_mode
)
st.caption(f"模式：{mode_label} | 交易所：{cfg.exchange.name}")

if control.get("kill_switch") == "true":
    st.error("紧急停止已开启：任何交易动作都会被拦截。")
elif control.get("paused") == "true":
    st.warning("机器人已暂停：恢复前不会执行交易。")
elif cfg.trading_mode == "live":
    st.error("真实实盘模式：如果所有安全门槛都通过，可能发送真实订单。")
else:
    st.success("当前是安全模式，可以先放心熟悉界面。")

app = TradingApp(cfg)

snapshot = repo.latest_snapshot()
positions = list(repo.list_positions().values())
orders = repo.list_recent_orders(50)
signals = repo.list_recent_signals(50)
risks = repo.list_recent_risk_events(50)
curve = repo.equity_curve(30)
review = repo.latest_review()
performance = summarize_performance(orders, curve, cfg.portfolio.initial_cash)

equity = float(snapshot["equity"]) if snapshot else cfg.portfolio.initial_cash
cash = float(snapshot["cash"]) if snapshot else cfg.portfolio.initial_cash
positions_value = float(snapshot["positions_value"]) if snapshot else 0.0
daily_pnl = float(snapshot["daily_pnl"]) if snapshot else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("总资产", f"{equity:.2f} {cfg.portfolio.quote_currency}")
c2.metric("现金", f"{cash:.2f}")
c3.metric("持仓价值", f"{positions_value:.2f}")
c4.metric("今日盈亏", f"{daily_pnl:.2f}")

tab_controls, tab_overview, tab_positions, tab_signals, tab_risk, tab_review, tab_config = st.tabs(
    ["操作", "资产曲线", "持仓", "信号", "风控", "复盘", "配置"]
)

with tab_controls:
    st.subheader("常用操作")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("刷新一轮", type="primary"):
        with st.spinner("正在跑一轮策略和风控..."):
            report = app.run_once()
        st.success(f"已刷新：{report}")
        st.rerun()
    if c2.button("暂停"):
        app.set_paused(True)
        st.warning("已暂停。")
        st.rerun()
    if c3.button("恢复"):
        app.set_paused(False)
        st.success("已恢复。")
        st.rerun()
    if c4.button("紧急停止"):
        app.set_kill_switch(True)
        st.error("紧急停止已开启。")
        st.rerun()

    if st.button("解除紧急停止"):
        app.set_kill_switch(False)
        st.success("紧急停止已解除。")
        st.rerun()

    st.divider()
    st.subheader("手动市价单")
    st.info("默认模拟盘不会动真实资金。真实实盘必须额外配置 .env，并输入确认文本。")
    symbol = st.selectbox("币种", cfg.exchange.symbols)
    side_label = st.segmented_control("方向", ["买入", "卖出"], default="买入")
    side = "buy" if side_label == "买入" else "sell"
    quote_qty = st.number_input(
        f"买入金额（{cfg.portfolio.quote_currency}）",
        min_value=0.0,
        value=min(float(cfg.execution.max_order_quote), 10.0),
        step=1.0,
    )
    live_confirm = ""
    if cfg.trading_mode == "live":
        st.warning("这可能发送真实订单。请确认你只用了小资金、现货、无提现权限 API key。")
        live_confirm = st.text_input("真实实盘下单前输入 EXECUTE_REAL_ORDER")
    if st.button("提交手动单", type="primary"):
        with st.spinner("正在提交风控检查后的订单..."):
            result = app.execute_manual_order(
                symbol=symbol,
                side=side,
                quote_qty=quote_qty if side == "buy" else None,
                confirmation_text=live_confirm,
            )
        st.info(result)
        st.rerun()

with tab_overview:
    st.subheader("绩效摘要")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("已平仓交易", performance.closed_trades)
    p2.metric("胜率", f"{performance.win_rate:.1%}")
    p3.metric("已实现盈亏", f"{performance.realized_pnl:.2f}")
    p4.metric("最大回撤", f"{performance.max_drawdown_pct:.2%}")
    p5, p6, p7, p8 = st.columns(4)
    profit_factor = "inf"
    if performance.profit_factor != float("inf"):
        profit_factor = f"{performance.profit_factor:.2f}"
    p5.metric("Profit Factor", profit_factor)
    p6.metric("手续费", f"{performance.fees:.4f}")
    p7.metric("收益率", f"{performance.return_pct:.2%}")
    p8.metric("状态", performance.status_label)
    st.divider()
    if not curve.empty:
        chart_df = curve.copy()
        chart_df["ts"] = pd.to_datetime(chart_df["ts"])
        st.line_chart(chart_df.set_index("ts")[["equity", "cash", "positions_value"]])
    else:
        st.info("还没有资产数据。点“操作”里的“刷新一轮”。")
    st.subheader("最近订单")
    st.dataframe(pd.DataFrame(orders), width="stretch", hide_index=True)

with tab_positions:
    st.dataframe(
        pd.DataFrame([p.__dict__ for p in positions]),
        width="stretch",
        hide_index=True,
    )

with tab_signals:
    st.dataframe(pd.DataFrame(signals), width="stretch", hide_index=True)

with tab_risk:
    latest_status = risks[0]["status"] if risks else "OK"
    if latest_status.startswith("REJECTED") or latest_status == "FAILED":
        st.error(latest_status)
    else:
        st.success(latest_status)
    st.dataframe(pd.DataFrame(risks), width="stretch", hide_index=True)

with tab_review:
    st.markdown(review["content"] if review else "还没有复盘。点“操作”里的“刷新一轮”。")

with tab_config:
    st.code(Path(_config_arg()).read_text(encoding="utf-8") if Path(_config_arg()).exists() else "")
