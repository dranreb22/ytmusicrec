from __future__ import annotations

from ytmusicrec.logging_setup import configure_logging
from ytmusicrec.settings import load_settings
from ytmusicrec.mssql import connect, ensure_schema


def main() -> None:
    configure_logging()
    s = load_settings()
    conn = connect(s)
    try:
        ensure_schema(conn)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        print("✅ MSSQL smoke test OK:", cur.fetchone()[0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
