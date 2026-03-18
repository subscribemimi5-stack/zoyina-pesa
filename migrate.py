"""
migrate.py — Ongeza tables mpya bila kupoteza data iliyopo
Endesha: python migrate.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'zoyina_pesa.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database haipatikani: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    print(f"Tables zilizopo: {sorted(existing)}")

    changes = []

    # ── 1. advertisement columns ──
    ad_cols = {r[1] for r in cur.execute("PRAGMA table_info(advertisement)").fetchall()}
    for col, defn in [
        ('group_id',      'INTEGER REFERENCES ad_group(id)'),
        ('platform',      "TEXT DEFAULT 'other'"),
        ('watch_seconds', 'INTEGER DEFAULT 60'),
        ('order_num',     'INTEGER DEFAULT 0'),
    ]:
        if col not in ad_cols:
            cur.execute(f"ALTER TABLE advertisement ADD COLUMN {col} {defn}")
            changes.append(f"advertisement.{col}")

    # ── 2. user columns (bot protection) ──
    user_cols = {r[1] for r in cur.execute("PRAGMA table_info(user)").fetchall()}
    for col, defn in [
        ('login_attempts', 'INTEGER DEFAULT 0'),
        ('locked_until',   'DATETIME'),
        ('last_login_at',  'DATETIME'),
    ]:
        if col not in user_cols:
            cur.execute(f"ALTER TABLE user ADD COLUMN {col} {defn}")
            changes.append(f"user.{col}")

    # ── 3. ad_group table ──
    if 'ad_group' not in existing:
        cur.execute("""
            CREATE TABLE ad_group (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                platform TEXT DEFAULT 'other',
                description TEXT,
                watch_seconds INTEGER DEFAULT 60,
                reward_per_ad REAL DEFAULT 500.0,
                min_level INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        changes.append("table: ad_group (mpya)")

    # ── 4. user_group_progress table ──
    if 'user_group_progress' not in existing:
        cur.execute("""
            CREATE TABLE user_group_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES user(id),
                group_id INTEGER NOT NULL REFERENCES ad_group(id),
                completed_at DATETIME,
                date_key TEXT NOT NULL
            )
        """)
        changes.append("table: user_group_progress (mpya)")

    # ── 5. rate_limit table ──
    if 'rate_limit' not in existing:
        cur.execute("""
            CREATE TABLE rate_limit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                action TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                window_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                blocked_until DATETIME,
                UNIQUE(ip_address, action)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_ip ON rate_limit(ip_address)")
        changes.append("table: rate_limit (mpya)")

    # ── 6. article table ──
    if 'article' not in existing:
        cur.execute("""
            CREATE TABLE article (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'finance',
                summary TEXT,
                content TEXT NOT NULL,
                image_filename TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        changes.append("table: article (mpya)")

    conn.commit()
    conn.close()

    if changes:
        print(f"\n✅ Migration imefanikiwa! Mabadiliko ({len(changes)}):")
        for c in changes:
            print(f"   ✓ {c}")
    else:
        print("\n✅ Database iko sawa — hakuna mabadiliko yanayohitajika.")

    return True

if __name__ == '__main__':
    print("=" * 50)
    print("Zoyina Pesa — Database Migration")
    print("=" * 50)
    success = migrate()
    if success:
        print("\n🚀 Sasa unaweza kuanza server: python app.py")
    else:
        print("\n❌ Migration imeshindwa!")
