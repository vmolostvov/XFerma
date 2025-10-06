from typing import Iterable, Sequence, Tuple, Dict, List, Optional, Set
from datetime import datetime
import psycopg, platform
from psycopg.rows import dict_row
from config import DB_PORT, DB_HOST_SERVER, DB_HOST_LOCAL, DB_PASSWORD, DB_BASE_NAME, DB_USERNAME


def get_host():
    system = platform.system().lower()
    if system == "linux":
        return DB_HOST_SERVER
    elif system == "darwin":
        return DB_HOST_LOCAL


class Database:
    def __init__(self, dsn=f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{get_host()}:{DB_PORT}/{DB_BASE_NAME}"):
        """
        dsn пример: "postgresql://user:pass@host:5432/dbname"
        """
        self.dsn = dsn

    def _conn(self):
        # dict_row -> cursor.fetchall() вернёт dict'ы
        return psycopg.connect(self.dsn, row_factory=dict_row)

    # =======================
    #  X_FERMA (основные методы)
    # =======================

    def insert_new_acc(
        self,
        uid: str,
        username: Optional[str],
        category: Optional[str],
        lang: Optional[str],
        pw: Optional[str],
        auth_token: Optional[str],
        ua: Optional[str],
        proxy: Optional[str],
    ) -> bool:
        """
        Вставка записи в X_FERMA.
        Если нужен UPSERT (не «already exist»), можем добавить ON CONFLICT(...) DO UPDATE.
        """
        sql = """
        INSERT INTO X_FERMA (uid, username, category, lang, addition_date, pass, auth_token, ua, proxy)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(sql, (uid, username, category, lang, datetime.now(), pw, auth_token, ua, proxy))
            return True
        except Exception as e:
            # Логируй, если нужно
            # print("insert_new_acc error:", e)
            return False  # эквивалент твоего "already exist", но без текста

    def update_avatar(self, uid: str, avatar_fn: str) -> bool:
        sql = "UPDATE X_FERMA SET avatar = %s WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (avatar_fn, uid))
            return cur.fetchone() is not None

    def update_desc_id(self, uid: str, desc_id: str) -> bool:
        sql = "UPDATE X_FERMA SET description_id = %s WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (desc_id, uid))
            return cur.fetchone() is not None

    def update_is_banned(self, uid: str) -> bool:
        sql = "UPDATE X_FERMA SET is_banned = TRUE WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (uid,))
            return cur.fetchone() is not None

    def update_is_banned_by_sn(self, screen_name: str) -> bool:
        sql = "UPDATE X_FERMA SET is_banned = TRUE WHERE screen_name = %s RETURNING screen_name;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (screen_name,))
            return cur.fetchone() is not None

    def delete_banned_by_uid(self, uid: str):
        sql = "DELETE FROM X_FERMA WHERE uid = %s;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (uid,))
            deleted = cur.rowcount
            if deleted > 0:
                print(f"✅ Удалено {deleted} записей")
            else:
                print("⚠️ Ничего не удалено (uid не найден)")

    def get_banned_accounts(self) -> List[dict]:
        """
        Возвращает неактивные аккаунты из X_FERMA.
        """
        base_sql = """
            SELECT *
            FROM X_FERMA
            WHERE is_banned IS TRUE
        """

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(base_sql)
            rows = cur.fetchall()

        return [
            {
                "uid": r["uid"],
                "screen_name": r["username"],
                "avatar": r["avatar"],
                "description_id": r["description_id"],
                "ua": r.get("ua"),
                "proxy": r.get("proxy"),
            }
            for r in rows
        ]

    def get_working_accounts(self, count: int | None = None) -> List[dict]:
        """
        Возвращает активные аккаунты из X_FERMA.
        Если count=None → вернёт все.
        """
        base_sql = """
            SELECT uid, username AS screen_name, ua, proxy
            FROM X_FERMA
            WHERE is_banned IS NOT TRUE
            ORDER BY addition_date DESC
        """

        if count is not None:
            sql = base_sql + " LIMIT %s"
            params = (count,)
        else:
            sql = base_sql
            params = ()

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        return [
            {
                "uid": r["uid"],
                "screen_name": r["screen_name"],
                "ua": r.get("ua"),
                "proxy": r.get("proxy"),
            }
            for r in rows
        ]

    # ==================================
    #  Accounts / follow_edges (очередь)
    # ==================================

    # ---- Accounts ----

    def fetch_all_accounts(self) -> List[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT uid, username AS screen_name, is_new FROM X_FERMA WHERE is_banned IS NOT TRUE;")
            return list(cur.fetchall())

    def fetch_new_accounts(self) -> List[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT uid, username AS screen_name, is_new, ua, proxy FROM X_FERMA "
                        "WHERE is_banned IS NOT TRUE "
                        "AND is_new IS TRUE;")
            return list(cur.fetchall())

    def fetch_accounts_by_ids(self, ids: Set[str]) -> List[dict]:
        if not ids:
            return []
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT uid, username AS screen_name, is_new, ua, proxy FROM X_FERMA WHERE uid = ANY(%s);",
                (list(ids),)
            )
            return list(cur.fetchall())

    def set_is_new_false(self, ids: Sequence[str]):
        if not ids:
            return
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE X_FERMA SET is_new = FALSE WHERE uid = ANY(%s);",
                (list(ids),)
            )

    # ---- Follow edges queue ----
    def upsert_follow_edge(self, src_id: str, dst_id: str):
        if src_id == dst_id:
            return
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO follow_edges(src_id, dst_id, status)
                VALUES (%s, %s, 'pending')
                ON CONFLICT (src_id, dst_id) DO NOTHING;
            """, (src_id, dst_id))

    def bulk_upsert_follow_edges(self, pairs: Sequence[Tuple[str, str]]):
        if not pairs:
            return
        pairs = list({(a, b) for a, b in pairs if a != b})
        if not pairs:
            return
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE tmp_edges(src_id BIGINT, dst_id BIGINT) ON COMMIT DROP;
            """)
            cur.executemany("INSERT INTO tmp_edges VALUES (%s, %s);", pairs)
            cur.execute("""
                INSERT INTO follow_edges(src_id, dst_id, status)
                SELECT src_id, dst_id, 'pending' FROM tmp_edges
                ON CONFLICT (src_id, dst_id) DO NOTHING;
            """)

    def fetch_pending_edges(self, limit: int = 100) -> List[Tuple[str, str]]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT src_id, dst_id
                FROM follow_edges
                WHERE status = 'pending'
                ORDER BY updated_at ASC
                LIMIT %s;
            """, (limit,))
            rows = cur.fetchall()
            return [(r["src_id"], r["dst_id"]) for r in rows]

    def mark_edge_done(self, src_id: str, dst_id: str):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE follow_edges
                SET status='done', last_error=NULL, updated_at=NOW()
                WHERE src_id=%s AND dst_id=%s;
            """, (src_id, dst_id))

    def mark_edge_failed(self, src_id: str, dst_id: str, error_msg: str):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE follow_edges
                SET status='failed', last_error=%s, updated_at=NOW()
                WHERE src_id=%s AND dst_id=%s;
            """, (error_msg[:1000], src_id, dst_id))

    def fetch_ready_to_unset_new(self) -> List[str]:
        """
        ID аккаунтов, у которых нет рёбер со статусом != 'done'
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT a.uid
                FROM accounts a
                WHERE a.is_new = TRUE
                  AND NOT EXISTS (
                        SELECT 1 FROM follow_edges fe
                        WHERE (fe.src_id = a.uid OR fe.dst_id = a.uid)
                          AND fe.status <> 'done'
                  );
            """)
            return [r["uid"] for r in cur.fetchall()]


if __name__ == '__main__':
    db = Database()
    print(db.get_banned_accounts())