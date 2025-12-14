import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.environ.get("RENNY_DB_PATH", os.path.join(os.path.dirname(__file__), "app.db"))


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_buy_price REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_user_id ON portfolio_holdings(user_id);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_profile (
                user_id TEXT PRIMARY KEY,
                horizon TEXT NOT NULL,
                risk TEXT NOT NULL,
                style TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                summary_markdown TEXT,
                error_message TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_analysis_user_id ON portfolio_analysis(user_id);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS holding_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_analysis_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                horizon TEXT NOT NULL,
                risk TEXT NOT NULL,
                style TEXT NOT NULL,
                tool_payload_json TEXT,
                strategy_markdown TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(portfolio_analysis_id) REFERENCES portfolio_analysis(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_holding_analysis_pa_id ON holding_analysis(portfolio_analysis_id);"
        )

        # Historical candles fetched from Upstox for simulation seeding
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS historical_candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(symbol, timestamp)
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_historical_candles_symbol ON historical_candles(symbol);")

        # Simulated trades log (with real-time streaming to UI)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);")

        # Current simulated positions
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sim_positions (
                user_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_price REAL NOT NULL,
                unrealized_pnl REAL,
                stop_loss REAL,
                take_profit REAL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, symbol),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        # Lightweight migrations for sim_positions
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sim_positions);").fetchall()]
        if "stop_loss" not in cols:
            conn.execute("ALTER TABLE sim_positions ADD COLUMN stop_loss REAL")
        if "take_profit" not in cols:
            conn.execute("ALTER TABLE sim_positions ADD COLUMN take_profit REAL")

        conn.commit()


@contextmanager
def get_conn(db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_user(user_id: str, db_path: str = DEFAULT_DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, ?)",
            (user_id, _utc_now_iso()),
        )


def replace_holdings(user_id: str, holdings: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> None:
    ensure_user(user_id, db_path=db_path)
    now = _utc_now_iso()
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM portfolio_holdings WHERE user_id = ?", (user_id,))
        for h in holdings:
            conn.execute(
                """
                INSERT INTO portfolio_holdings (user_id, symbol, quantity, avg_buy_price, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    str(h.get("symbol", "")).strip().upper(),
                    float(h.get("quantity", 0)),
                    float(h.get("avg_buy_price", 0)),
                    now,
                ),
            )


def upsert_trading_profile(user_id: str, profile: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> None:
    ensure_user(user_id, db_path=db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trading_profile (user_id, horizon, risk, style, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                horizon=excluded.horizon,
                risk=excluded.risk,
                style=excluded.style,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                str(profile.get("horizon")),
                str(profile.get("risk")),
                str(profile.get("style")),
                _utc_now_iso(),
            ),
        )


def fetch_holdings(user_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT symbol, quantity, avg_buy_price FROM portfolio_holdings WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_trading_profile(user_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT horizon, risk, style, updated_at FROM trading_profile WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def create_portfolio_analysis(user_id: str, status: str = "running", db_path: str = DEFAULT_DB_PATH) -> int:
    ensure_user(user_id, db_path=db_path)
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO portfolio_analysis (user_id, created_at, status) VALUES (?, ?, ?)",
            (user_id, _utc_now_iso(), status),
        )
        return int(cur.lastrowid)


def add_holding_analysis(
    portfolio_analysis_id: int,
    symbol: str,
    horizon: str,
    risk: str,
    style: str,
    tool_payload_json: Optional[str],
    strategy_markdown: Optional[str],
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO holding_analysis (
                portfolio_analysis_id, symbol, horizon, risk, style,
                tool_payload_json, strategy_markdown, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(portfolio_analysis_id),
                str(symbol).strip().upper(),
                str(horizon),
                str(risk),
                str(style),
                tool_payload_json,
                strategy_markdown,
                _utc_now_iso(),
            ),
        )
        return int(cur.lastrowid)


def finalize_portfolio_analysis(
    portfolio_analysis_id: int,
    status: str,
    summary_markdown: Optional[str] = None,
    error_message: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE portfolio_analysis
            SET status = ?, summary_markdown = ?, error_message = ?
            WHERE id = ?
            """,
            (status, summary_markdown, error_message, int(portfolio_analysis_id)),
        )


def fetch_portfolio_analysis(portfolio_analysis_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        pa = conn.execute(
            "SELECT id, user_id, created_at, status, summary_markdown, error_message FROM portfolio_analysis WHERE id = ?",
            (int(portfolio_analysis_id),),
        ).fetchone()
        if not pa:
            return None

        holdings = conn.execute(
            """
            SELECT symbol, horizon, risk, style, tool_payload_json, strategy_markdown, created_at
            FROM holding_analysis
            WHERE portfolio_analysis_id = ?
            ORDER BY id ASC
            """,
            (int(portfolio_analysis_id),),
        ).fetchall()

        out = dict(pa)
        out["holding_analyses"] = [dict(r) for r in holdings]
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Historical Candles (for simulation seeding)
# ─────────────────────────────────────────────────────────────────────────────

def upsert_historical_candles(candles: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """Insert or update historical candles. Returns count of inserted rows."""
    if not candles:
        return 0
    with get_conn(db_path) as conn:
        count = 0
        for c in candles:
            conn.execute(
                """
                INSERT INTO historical_candles (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
                """,
                (
                    str(c.get("symbol", "")).strip().upper(),
                    str(c.get("timestamp", "")),
                    float(c.get("open", 0)),
                    float(c.get("high", 0)),
                    float(c.get("low", 0)),
                    float(c.get("close", 0)),
                    float(c.get("volume", 0)),
                ),
            )
            count += 1
        return count


def fetch_historical_candles(symbol: str, limit: int = 500, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch historical candles for a symbol, ordered by timestamp ascending."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT symbol, timestamp, open, high, low, close, volume
            FROM historical_candles
            WHERE symbol = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (symbol.strip().upper(), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_last_candle(symbol: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Get the most recent candle for a symbol."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT symbol, timestamp, open, high, low, close, volume
            FROM historical_candles
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol.strip().upper(),),
        ).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Trades (agent trade log)
# ─────────────────────────────────────────────────────────────────────────────

def insert_trade(
    user_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    reason: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Insert a trade record. Returns the trade ID."""
    ensure_user(user_id, db_path=db_path)
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO trades (user_id, symbol, side, quantity, price, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                str(symbol).strip().upper(),
                side.lower(),
                float(quantity),
                float(price),
                reason,
                _utc_now_iso(),
            ),
        )
        return int(cur.lastrowid)


def fetch_trades(user_id: str, limit: int = 100, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch trades for a user, most recent first."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, symbol, side, quantity, price, reason, created_at
            FROM trades
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Simulated Positions
# ─────────────────────────────────────────────────────────────────────────────

def upsert_sim_position(
    user_id: str,
    symbol: str,
    quantity: float,
    avg_price: float,
    unrealized_pnl: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Insert or update a simulated position."""
    ensure_user(user_id, db_path=db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sim_positions (user_id, symbol, quantity, avg_price, unrealized_pnl, stop_loss, take_profit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, symbol) DO UPDATE SET
                quantity=excluded.quantity,
                avg_price=excluded.avg_price,
                unrealized_pnl=excluded.unrealized_pnl,
                stop_loss=excluded.stop_loss,
                take_profit=excluded.take_profit,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                str(symbol).strip().upper(),
                float(quantity),
                float(avg_price),
                unrealized_pnl,
                stop_loss,
                take_profit,
                _utc_now_iso(),
            ),
        )


def fetch_sim_positions(user_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all simulated positions for a user."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT user_id, symbol, quantity, avg_price, unrealized_pnl, stop_loss, take_profit, updated_at
            FROM sim_positions
            WHERE user_id = ?
            ORDER BY symbol ASC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_users_with_sim_positions(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """Fetch distinct user IDs that currently have any simulated positions."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM sim_positions ORDER BY user_id ASC"
        ).fetchall()
        return [str(r[0]) for r in rows]


def delete_sim_position(user_id: str, symbol: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Delete a simulated position (e.g., when fully sold)."""
    with get_conn(db_path) as conn:
        conn.execute(
            "DELETE FROM sim_positions WHERE user_id = ? AND symbol = ?",
            (user_id, symbol.strip().upper()),
        )


def clear_sim_positions(user_id: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Clear all simulated positions for a user."""
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM sim_positions WHERE user_id = ?", (user_id,))

