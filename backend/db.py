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
