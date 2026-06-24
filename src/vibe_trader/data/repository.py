from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from vibe_trader.config.schema import AppConfig
from vibe_trader.models import OrderResult, PortfolioState, Position, TradingSignal


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteRepository:
    def __init__(self, config: AppConfig):
        self.config = config
        self.path = config.resolve_path(config.database.path)

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists run_events (
                  run_id text primary key,
                  started_at text not null,
                  finished_at text,
                  status text not null,
                  message text
                );

                create table if not exists market_candles (
                  symbol text not null,
                  timeframe text not null,
                  ts text not null,
                  open real not null,
                  high real not null,
                  low real not null,
                  close real not null,
                  volume real not null,
                  created_at text not null,
                  primary key (symbol, timeframe, ts)
                );

                create table if not exists signals (
                  id integer primary key autoincrement,
                  run_id text not null,
                  symbol text not null,
                  ts text not null,
                  action text not null,
                  confidence real not null,
                  reason text not null,
                  details_json text not null
                );

                create table if not exists orders (
                  id integer primary key autoincrement,
                  run_id text not null,
                  symbol text not null,
                  side text not null,
                  order_type text not null,
                  status text not null,
                  qty real not null,
                  price real not null,
                  filled_qty real not null,
                  avg_price real not null,
                  fee real not null,
                  reason text not null,
                  exchange_order_id text,
                  message text,
                  created_at text not null,
                  updated_at text not null
                );

                create table if not exists positions (
                  symbol text primary key,
                  side text not null,
                  qty real not null,
                  entry_price real not null,
                  mark_price real not null,
                  realized_pnl real not null,
                  unrealized_pnl real not null,
                  opened_at text not null,
                  updated_at text not null,
                  stop_loss real not null,
                  take_profit real not null
                );

                create table if not exists portfolio_snapshots (
                  id integer primary key autoincrement,
                  ts text not null,
                  equity real not null,
                  cash real not null,
                  positions_value real not null,
                  daily_pnl real not null,
                  details_json text not null
                );

                create table if not exists risk_events (
                  id integer primary key autoincrement,
                  run_id text not null,
                  symbol text,
                  rule text not null,
                  status text not null,
                  message text not null,
                  details_json text not null,
                  created_at text not null
                );

                create table if not exists reviews (
                  review_date text primary key,
                  content text not null,
                  created_at text not null
                );

                create table if not exists bot_control (
                  key text primary key,
                  value text not null,
                  updated_at text not null
                );
                """
            )

    def start_run(self, run_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert or replace into run_events(run_id, started_at, status, message)
                values (?, ?, ?, ?)
                """,
                (run_id, utc_now_iso(), "RUNNING", ""),
            )

    def finish_run(self, run_id: str, status: str, message: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                update run_events
                set finished_at = ?, status = ?, message = ?
                where run_id = ?
                """,
                (utc_now_iso(), status, message, run_id),
            )

    def upsert_candles(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> int:
        if candles.empty:
            return 0
        rows = []
        for item in candles.reset_index().to_dict("records"):
            ts = item.get("timestamp") or item.get("index")
            if isinstance(ts, pd.Timestamp):
                ts = ts.to_pydatetime().replace(tzinfo=UTC).isoformat()
            rows.append(
                (
                    symbol,
                    timeframe,
                    str(ts),
                    float(item["open"]),
                    float(item["high"]),
                    float(item["low"]),
                    float(item["close"]),
                    float(item["volume"]),
                    utc_now_iso(),
                )
            )
        with self.connect() as conn:
            conn.executemany(
                """
                insert or replace into market_candles
                (symbol, timeframe, ts, open, high, low, close, volume, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def load_candles(self, symbol: str, timeframe: str, limit: int = 260) -> pd.DataFrame:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select ts, open, high, low, close, volume
                from market_candles
                where symbol = ? and timeframe = ?
                order by ts desc
                limit ?
                """,
                (symbol, timeframe, limit),
            ).fetchall()
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.DataFrame([dict(r) for r in rows])
        df["timestamp"] = pd.to_datetime(df["ts"], utc=True)
        df = df.drop(columns=["ts"]).sort_values("timestamp").set_index("timestamp")
        return df.astype(float)

    def insert_signal(self, signal: TradingSignal) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into signals(run_id, symbol, ts, action, confidence, reason, details_json)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.run_id,
                    signal.symbol,
                    signal.created_at.replace(tzinfo=UTC).isoformat(),
                    signal.action,
                    signal.confidence,
                    signal.reason,
                    json.dumps(signal.details, ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def insert_order(self, order: OrderResult) -> int:
        now = utc_now_iso()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into orders(
                  run_id, symbol, side, order_type, status, qty, price, filled_qty,
                  avg_price, fee, reason, exchange_order_id, message, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.run_id,
                    order.symbol,
                    order.side,
                    order.order_type,
                    order.status,
                    order.qty,
                    order.price,
                    order.filled_qty,
                    order.avg_price,
                    order.fee,
                    order.reason,
                    order.exchange_order_id,
                    order.message,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def upsert_position(self, position: Position) -> None:
        with self.connect() as conn:
            if position.qty <= 0:
                conn.execute("delete from positions where symbol = ?", (position.symbol,))
                return
            conn.execute(
                """
                insert or replace into positions(
                  symbol, side, qty, entry_price, mark_price, realized_pnl, unrealized_pnl,
                  opened_at, updated_at, stop_loss, take_profit
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position.symbol,
                    position.side,
                    position.qty,
                    position.entry_price,
                    position.mark_price,
                    position.realized_pnl,
                    position.unrealized_pnl,
                    position.opened_at or utc_now_iso(),
                    position.updated_at or utc_now_iso(),
                    position.stop_loss,
                    position.take_profit,
                ),
            )

    def list_positions(self) -> dict[str, Position]:
        with self.connect() as conn:
            rows = conn.execute("select * from positions order by symbol").fetchall()
        return {row["symbol"]: Position(**dict(row)) for row in rows}

    def insert_snapshot(self, state: PortfolioState, details: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into portfolio_snapshots(
                  ts, equity, cash, positions_value, daily_pnl, details_json
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now_iso(),
                    state.equity,
                    state.cash,
                    state.positions_value,
                    state.daily_pnl,
                    json.dumps(details or {}, ensure_ascii=False, default=str),
                ),
            )

    def latest_snapshot(self) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "select * from portfolio_snapshots order by ts desc limit 1"
            ).fetchone()

    def insert_risk_event(
        self,
        run_id: str,
        symbol: str | None,
        rule: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into risk_events(
                  run_id, symbol, rule, status, message, details_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    symbol,
                    rule,
                    status,
                    message,
                    json.dumps(details or {}, ensure_ascii=False, default=str),
                    utc_now_iso(),
                ),
            )

    def list_recent_orders(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from orders order by created_at desc limit ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_today_orders(self) -> list[dict[str, Any]]:
        since = datetime.now(UTC).date().isoformat()
        with self.connect() as conn:
            rows = conn.execute(
                "select * from orders where created_at >= ? order by created_at desc", (since,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recent_signals(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from signals order by ts desc limit ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recent_risk_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from risk_events order by created_at desc limit ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def last_order_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from orders where symbol = ? order by created_at desc limit 1", (symbol,)
            ).fetchone()
        return dict(row) if row else None

    def open_orders_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select * from orders
                where symbol = ? and status in ('open', 'submitted', 'partial')
                order by created_at desc
                """,
                (symbol,),
            ).fetchall()
        return [dict(row) for row in rows]

    def consecutive_loss_count(self, lookback: int = 10) -> int:
        orders = self.list_recent_orders(lookback)
        losses = 0
        for order in orders:
            if order["side"] != "sell" or order["status"] != "filled":
                continue
            message = order.get("message") or "{}"
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                payload = {}
            pnl = float(payload.get("realized_pnl", 0.0))
            if pnl < 0:
                losses += 1
            else:
                break
        return losses

    def today_realized_pnl(self) -> float:
        pnl = 0.0
        for order in self.list_today_orders():
            try:
                payload = json.loads(order.get("message") or "{}")
            except json.JSONDecodeError:
                payload = {}
            pnl += float(payload.get("realized_pnl", 0.0))
        return pnl

    def save_review(self, review_date: str, content: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert or replace into reviews(review_date, content, created_at)
                values (?, ?, ?)
                """,
                (review_date, content, utc_now_iso()),
            )

    def latest_review(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from reviews order by review_date desc limit 1").fetchone()
        return dict(row) if row else None

    def set_control(self, key: str, value: str | bool) -> None:
        normalized = str(value).lower() if isinstance(value, bool) else str(value)
        with self.connect() as conn:
            conn.execute(
                """
                insert or replace into bot_control(key, value, updated_at)
                values (?, ?, ?)
                """,
                (key, normalized, utc_now_iso()),
            )

    def get_control(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("select key, value from bot_control").fetchall()
        values = {row["key"]: row["value"] for row in rows}
        values.setdefault("paused", "false")
        values.setdefault("kill_switch", "false")
        return values

    def equity_curve(self, days: int = 30) -> pd.DataFrame:
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self.connect() as conn:
            rows = conn.execute(
                """
                select ts, equity, cash, positions_value, daily_pnl
                from portfolio_snapshots
                where ts >= ?
                order by ts asc
                """,
                (since,),
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])
