import sqlite3
from pathlib import Path

DB_PATH = Path("nawaf.sqlite3")


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            announcement_channel INTEGER,
            ad_channel INTEGER,
            application_channel INTEGER,
            application_review_channel INTEGER,
            dhikr_channel INTEGER,
            dhikr_enabled INTEGER DEFAULT 0,
            dhikr_interval INTEGER DEFAULT 3600,
            currency_name TEXT DEFAULT 'Nawaf Coin',
            currency_symbol TEXT DEFAULT '🪙',
            ticket_category INTEGER,
            ticket_log_channel INTEGER,
            ticket_panel_channel INTEGER,
            ticket_panel_message INTEGER,
            application_panel_channel INTEGER,
            application_panel_message INTEGER,
            shop_order_channel INTEGER
        );
        CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            closed_by INTEGER,
            closed_at TEXT,
            rating INTEGER,
            note TEXT
        );
        CREATE TABLE IF NOT EXISTS xp (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reviewer_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS balances (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            balance INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS shop_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER NOT NULL,
            stock INTEGER DEFAULT -1,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # Safe schema upgrade for databases created by older Nawaf versions.
        columns = {row[1] for row in con.execute("PRAGMA table_info(guild_config)")}
        if "shop_order_channel" not in columns:
            con.execute("ALTER TABLE guild_config ADD COLUMN shop_order_channel INTEGER")


def ensure_guild(guild_id):
    with connect() as con:
        con.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))


def get_config(guild_id):
    ensure_guild(guild_id)
    with connect() as con:
        return con.execute("SELECT * FROM guild_config WHERE guild_id=?", (guild_id,)).fetchone()


def set_config(guild_id, **values):
    ensure_guild(guild_id)
    allowed = set(get_config(guild_id).keys()) - {"guild_id"}
    values = {k: v for k, v in values.items() if k in allowed}
    if not values:
        return
    fields = ", ".join(f"{k}=?" for k in values)
    with connect() as con:
        con.execute(f"UPDATE guild_config SET {fields} WHERE guild_id=?", (*values.values(), guild_id))
