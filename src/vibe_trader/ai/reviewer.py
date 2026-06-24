from __future__ import annotations

from datetime import UTC, datetime

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.repository import SQLiteRepository


class DailyReviewer:
    def __init__(self, config: AppConfig, repo: SQLiteRepository):
        self.config = config
        self.repo = repo

    def generate(self) -> str:
        if self.config.ai.provider == "openai":
            return self._openai_review()
        return self._local_review()

    def _local_review(self) -> str:
        orders = self.repo.list_today_orders()
        signals = self.repo.list_recent_signals(20)
        risks = self.repo.list_recent_risk_events(20)
        filled = [o for o in orders if o["status"] == "filled"]
        rejected = [o for o in orders if o["status"] == "rejected"]
        pnl = self.repo.today_realized_pnl()
        date = datetime.now(UTC).date().isoformat()
        lines = [
            f"### {date} Local Review",
            f"- 今日成交：{len(filled)} 笔；拒单/失败：{len(rejected)} 笔；已实现盈亏：{pnl:.2f}。",
            f"- 最近信号：{len(signals)} 条；最近风控事件：{len(risks)} 条。",
        ]
        if risks:
            top = risks[0]
            lines.append(f"- 最新风控状态：{top['status']}，原因：{top['message']}。")
        if not filled:
            lines.append("- 今天没有真实成交，重点检查信号质量、风控拦截是否符合预期。")
        else:
            reasons = "；".join(o["reason"] for o in filled[:3])
            lines.append(f"- 代表性交易原因：{reasons}")
        lines.append("- 参数建议：先观察，不自动修改参数；任何调整都应走回测和 sandbox 验证。")
        return "\n".join(lines)

    def _openai_review(self) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            return (
                self._local_review()
                + "\n- OpenAI package not installed; fell back to local review."
            )

        orders = self.repo.list_today_orders()
        signals = self.repo.list_recent_signals(30)
        risks = self.repo.list_recent_risk_events(30)
        prompt = (
            "You are reviewing a crypto paper/sandbox trading bot. "
            "Do not promise profit. Do not suggest bypassing risk controls. "
            "Summarize behavior, risks, bugs, and conservative parameter ideas in Chinese.\n\n"
            f"Orders: {orders}\nSignals: {signals}\nRisks: {risks}"
        )
        client = OpenAI()
        model = self.config.ai.model or "gpt-4.1-mini"
        response = client.responses.create(model=model, input=prompt)
        return response.output_text
