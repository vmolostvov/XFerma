from typing import Iterable, Sequence, Tuple, Dict, List, Optional, Set
from datetime import datetime, timedelta, timezone
import psycopg, platform, logging, random, json
from psycopg.rows import dict_row
from config import DB_PORT, DB_HOST_SERVER, DB_HOST_LOCAL, DB_PASSWORD, DB_BASE_NAME, DB_USERNAME, get_proxy_by_sid
from zoneinfo import ZoneInfo

MOS_TZ = ZoneInfo("Europe/Moscow")

logger = logging.getLogger("xFerma")

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
        proxy_sid: Optional[str],
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
                cur.execute(sql, (uid, username, category, lang, datetime.now(), pw, auth_token, ua, proxy_sid))
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
        sql = "UPDATE X_FERMA SET is_banned = TRUE WHERE username = %s RETURNING username;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (screen_name,))
            return cur.fetchone() is not None

    def delete_banned_by_uid(self, uid: str):
        sql = "DELETE FROM X_FERMA WHERE uid = %s;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (uid,))
            deleted = cur.rowcount
            if deleted > 0:
                logger.info(f"✅ Удалено {deleted} записей")
            else:
                logger.warning("⚠️ Ничего не удалено (uid не найден)")

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
                "proxy": get_proxy_by_sid(r.get("proxy")),
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
            AND is_influencer IS NOT TRUE
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
                "proxy": get_proxy_by_sid(r.get("proxy")),
            }
            for r in rows
        ]

    # ==================================
    #  Accounts / follow_edges (очередь)
    # ==================================

    # ---- Accounts ----

    def fetch_all_accounts(self):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT uid, username FROM X_FERMA WHERE is_banned IS NOT TRUE AND is_influencer IS NOT TRUE;")
            return [{"id": r['uid'], "screen_name": r['username']} for r in cur.fetchall()]

    def fetch_influencers_with_uid(self, path="influencers.jsonl"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            logger.warning("[SCHED] influencers.jsonl не найден")
            return []
        except json.JSONDecodeError as e:
            logger.exception(f"[SCHED] Ошибка чтения {path}: {e}")
            return []

        seen, uniq = set(), []
        for d in data:
            sn = d.get("screen_name", "").strip().lstrip("@")
            uid = int(d.get("uid"))
            if sn and sn not in seen:
                uniq.append({"screen_name": sn, "uid": uid})
                seen.add(sn)
        return uniq

    def count_done_today(self, src_id):
        now_eu = datetime.now(MOS_TZ)
        start_local = now_eu.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM follow_edges
                WHERE src_id=%s AND status='done' AND done_at >= %s AND done_at < %s;
            """, (src_id, start_utc, end_utc))
            row = cur.fetchone()
            return row["cnt"] if row else 0

    def count_pending_today(self, src_id):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM follow_edges
                WHERE src_id=%s AND status='pending';
            """, (src_id,))
            row = cur.fetchone()
            return row["cnt"] if row else 0

    def set_daily_quota_if_absent(self, src_id, plan_date, quota_min=3, quota_max=10):
        quota = random.randint(quota_min, quota_max)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO follow_daily_plan(src_id, plan_date, quota)
                VALUES (%s, %s, %s)
                ON CONFLICT (src_id, plan_date) DO NOTHING;
            """, (src_id, plan_date, quota))

    def get_daily_quota(self, src_id, plan_date, quota_min=3, quota_max=10):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT quota AS q FROM follow_daily_plan
                WHERE src_id=%s AND plan_date=%s;
            """, (src_id, plan_date))
            row = cur.fetchone()
            if row:
                return row["q"]
        # нет строки — создадим
        self.set_daily_quota_if_absent(src_id, plan_date, quota_min, quota_max)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT quota AS q FROM follow_daily_plan
                WHERE src_id=%s AND plan_date=%s;
            """, (src_id, plan_date))
            return cur.fetchone()["q"]

    def fetch_followed_or_pending_dst_ids(self, src_id):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT dst_id
                FROM follow_edges
                WHERE src_id=%s AND status IN ('pending','done');
            """, (src_id,))
            return {r["dst_id"] for r in cur.fetchall()}

    def bulk_upsert_follow_edges(self, pairs):
        if not pairs:
            return 0
        with self._conn() as conn, conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO follow_edges(src_id, dst_id, status, created_at)
                VALUES (%s, %s, 'pending', NOW())
                ON CONFLICT (src_id, dst_id) DO NOTHING;
            """, pairs)
            return cur.rowcount

    def fetch_new_accounts(self) -> List[dict]:
        """
        Возвращает новые аккаунты (is_new = TRUE), не забаненные и не инфлюенсеров.
        Поле proxy автоматически обрабатывается через get_proxy_by_sid().
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT uid, username AS screen_name, is_new, ua, proxy
                FROM X_FERMA
                WHERE is_banned IS NOT TRUE
                  AND is_new IS TRUE
                  AND is_influencer IS NOT TRUE;
            """)
            rows = cur.fetchall()

        return [
            {
                "uid": r["uid"],
                "screen_name": r["screen_name"],
                "is_new": r["is_new"],
                "ua": r.get("ua"),
                "proxy": get_proxy_by_sid(r.get("proxy"))
            }
            for r in rows
        ]

    def fetch_accounts_by_ids(self, ids: Set[str]) -> List[dict]:
        """
        Возвращает список аккаунтов по их uid.
        Значение proxy автоматически преобразуется через get_proxy_by_sid().
        """
        if not ids:
            return []

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT uid, username AS screen_name, is_new, ua, proxy
                FROM X_FERMA
                WHERE uid = ANY(%s);
                """,
                (list(ids),)
            )
            rows = cur.fetchall()

        return [
            {
                "uid": r["uid"],
                "screen_name": r["screen_name"],
                "is_new": r["is_new"],
                "ua": r.get("ua"),
                "proxy": get_proxy_by_sid(r.get("proxy"))
            }
            for r in rows
        ]

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
                SET status='done',
                    last_error=NULL,
                    updated_at=NOW(),
                    done_at=NOW()
                WHERE src_id=%s AND dst_id=%s;
            """, (src_id, dst_id))

    def mark_edge_failed(self, src_id: str, dst_id: str, error_msg: str):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE follow_edges
                SET status='failed', last_error=%s, updated_at=NOW()
                WHERE src_id=%s AND dst_id=%s;
            """, (error_msg[:1000], src_id, dst_id))

    def is_account_complete_strict(self, uid: str) -> bool:
        """
        Аккаунт готов, если:
          - исходящие DONE >= (все другие не-инфлюенсеры) + (все инфлюенсеры)
          - входящие DONE >= (все другие не-инфлюенсеры)
          - нет ребер со статусом <> 'done' для (src=uid или dst=uid)
        """
        with self._conn() as conn, conn.cursor() as cur:
            # Сколько рабочих аккаунтов (не инфлюенсеров), кроме self
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM X_FERMA
                WHERE is_banned IS NOT TRUE
                  AND is_influencer IS NOT TRUE
                  AND uid <> %s;
            """, (uid,))
            other_workers = cur.fetchone()["cnt"]

            # Сколько инфлюенсеров
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM X_FERMA
                WHERE is_influencer IS TRUE;
            """)
            influencers = cur.fetchone()["cnt"]

            expected_out = other_workers + influencers  # должен подписаться на всех
            expected_in = other_workers  # все рабочие должны подписаться на него

            # done исходящие
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM follow_edges
                WHERE src_id = %s AND status = 'done';
            """, (uid,))
            done_out = cur.fetchone()["cnt"]

            # done входящие: только от рабочих (не инфлюенсеров)
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM follow_edges fe
                JOIN X_FERMA a ON a.uid = fe.src_id
                WHERE fe.dst_id = %s
                  AND fe.status = 'done'
                  AND a.is_influencer IS NOT TRUE
                  AND a.is_banned IS NOT TRUE;
            """, (uid,))
            done_in = cur.fetchone()["cnt"]

            # существуют ли недоделанные ребра для этого аккаунта
            cur.execute("""
                SELECT EXISTS (
                  SELECT 1
                  FROM follow_edges
                  WHERE (src_id = %s OR dst_id = %s)
                    AND status <> 'done'
                ) AS has_not_done;
            """, (uid, uid))
            has_not_done = cur.fetchone()["has_not_done"]

            return (not has_not_done) and (done_out >= expected_out) and (done_in >= expected_in)

    def fetch_ready_to_unset_new_strict(self) -> list[str]:
        """
        Возвращает uid тех аккаунтов (не инфлюенсеров, is_new=TRUE),
        которые прошли строгую проверку готовности.
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT uid
                FROM X_FERMA
                WHERE is_new = TRUE
                  AND is_influencer IS NOT TRUE
                  AND is_banned IS NOT TRUE;
            """)
            candidates = [r["uid"] for r in cur.fetchall()]

        ready = []
        for uid in candidates:
            if self.is_account_complete_strict(uid):
                ready.append(uid)
        return ready

    def ensure_influencers_present(self, infls: list[dict]) -> int:
        """
        infls: [{"uid": "...", "screen_name": "..."}]
        """
        sql = """
        INSERT INTO X_FERMA (uid, username, is_influencer, addition_date)
        VALUES (%s, %s, TRUE, NOW())
        ON CONFLICT (uid) DO NOTHING;
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.executemany(sql, [(i["uid"], i["screen_name"]) for i in infls])
            return cur.rowcount


if __name__ == '__main__':
    db = Database()
    print(db.fetch_influencers_with_uid())