from typing import Iterable, Sequence, Tuple, Dict, List, Optional, Set
from datetime import datetime, timedelta, timezone
import psycopg, platform, logging, json, os
from psycopg.rows import dict_row
from config import *
from pixelscan_checker import get_proxy_by_sid
from zoneinfo import ZoneInfo

MOS_TZ = ZoneInfo("Europe/Moscow")

logger = logging.getLogger("xFerma")

MAX_ATTEMPTS = 10
BASE_DELAY_MINUTES = 5
MAX_DELAY_HOURS = 24


#TODO: on the server side need to add var export APP_ENV=server
#TODO: on the local side need to add var export APP_ENV=local
def is_server():
    return os.getenv("APP_ENV") == "server"


def get_host():
    return DB_HOST_SERVER if is_server() else DB_HOST_LOCAL


def get_port():
    return DB_PORT_SERVER if is_server() else DB_PORT_LOCAL


class Database:
    def __init__(self, dsn=f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{get_host()}:{get_port()}/{DB_BASE_NAME}"):
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

    def update_proxy(
            self,
            proxy: str,
            uid: str | None = None,
            un: str | None = None
    ) -> bool:
        """
        Обновляет proxy аккаунта.
        - Если передан un → обновляет по username
        - Иначе → обновляет по uid
        """

        if un:
            sql = """
                UPDATE X_FERMA
                SET proxy = %s
                WHERE username = %s
                RETURNING uid;
            """
            params = (proxy, un)

        else:
            if not uid:
                raise ValueError("uid is required if username is not provided")

            sql = """
                UPDATE X_FERMA
                SET proxy = %s
                WHERE uid = %s
                RETURNING uid;
            """
            params = (proxy, uid)

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() is not None

    def update_pw(self, uid: str, pw: str) -> bool:
        sql = "UPDATE X_FERMA SET pass = %s, pass_changed = True WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (pw, uid))
            return cur.fetchone() is not None

    def update_phone(self, username: str, phone: str) -> bool:
        sql = "UPDATE X_FERMA SET phone = %s WHERE LOWER(username) = LOWER(%s) RETURNING username;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (phone, username))
            return cur.fetchone() is not None

    def update_email(self, username: str, email: str, email_pass: str) -> bool:
        sql = "UPDATE X_FERMA SET email = %s, email_pass = %s, email_changed = True WHERE LOWER(username) = LOWER(%s) RETURNING username;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (email, email_pass, username))
            return cur.fetchone() is not None

    def update_auth(self, uid: str, auth_token: str) -> bool:
        sql = "UPDATE X_FERMA SET auth_token = %s, rs_attempts = 0 WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (auth_token, uid))
            return cur.fetchone() is not None

    def update_is_banned(self, uid: str) -> bool:
        sql = "UPDATE X_FERMA SET is_banned = TRUE WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (uid,))
            return cur.fetchone() is not None

    def update_is_locked(self, uid: str) -> bool:
        sql = "UPDATE X_FERMA SET is_locked = TRUE WHERE uid = %s RETURNING uid;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (uid,))
            return cur.fetchone() is not None

    def update_is_banned_by_sn(self, screen_name: str) -> bool:
        sql = "UPDATE X_FERMA SET is_banned = TRUE WHERE username = %s RETURNING username;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (screen_name,))
            return cur.fetchone() is not None

    def update_regen_session(self, uid: str, value: bool) -> bool:
        """
        Если value == True:
            UPDATE X_FERMA SET regen_sess = TRUE WHERE uid = ...
        Если value == False:
            UPDATE X_FERMA SET regen_sess = FALSE, rs_attempts = 0 WHERE uid = ...
        """
        if value:
            sql = """
                UPDATE X_FERMA 
                SET regen_sess = TRUE 
                WHERE uid = %s 
                RETURNING uid;
            """
            params = (uid,)
        else:
            sql = """
                UPDATE X_FERMA 
                SET regen_sess = FALSE,
                    rs_attempts = 0
                WHERE uid = %s 
                RETURNING uid;
            """
            params = (uid,)

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() is not None

    def increment_rs_attempts(self, uid: str):

        def _calc_backoff_delay(attempt: int) -> timedelta:
            """
            Экспоненциальный backoff с cap в 24 часа
            """
            minutes = BASE_DELAY_MINUTES * (2 ** (attempt - 1))
            max_minutes = MAX_DELAY_HOURS * 60
            return timedelta(minutes=min(minutes, max_minutes))

        """
        +1 попытка восстановления с растущим таймаутом.

        Возвращает:
            "ok" — попытка засчитана, выставлен таймаут
            "limit_reached" — достигнут лимит, аккаунт забанен
            "not_found" — uid нет
        """

        now = datetime.now()

        sql_inc = """
            UPDATE X_FERMA
            SET rs_attempts = COALESCE(rs_attempts, 0) + 1
            WHERE uid = %s
            RETURNING rs_attempts;
        """

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql_inc, (uid,))
            row = cur.fetchone()

            if not row:
                return "not_found"

            attempts = row["rs_attempts"]

            # 🚫 Лимит превышен → бан
            if attempts >= MAX_ATTEMPTS:
                sql_ban = """
                    UPDATE X_FERMA
                    SET is_banned = TRUE,
                        regen_sess = FALSE
                    WHERE uid = %s
                """
                cur.execute(sql_ban, (uid,))
                return "limit_reached"

            # ⏱️ Считаем таймаут
            delay = _calc_backoff_delay(attempts)
            next_try = now + delay

            sql_timeout = """
                UPDATE X_FERMA
                SET rs_next_try = %s
                WHERE uid = %s
            """
            cur.execute(sql_timeout, (next_try, uid))

            return "ok"

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
        Возвращает забаненые аккаунты из X_FERMA.
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

    def get_regen_sess_accounts(self) -> List[dict]:
        """
        Возвращает аккаунты, готовые к regen_sess
        (учтены таймауты и баны)
        """

        sql = """
            SELECT *
            FROM X_FERMA
            WHERE regen_sess IS TRUE
              AND is_banned IS NOT TRUE
              AND (
                    rs_next_try IS NULL
                    OR rs_next_try <= NOW()
              )
        """

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

        return [
            {
                "uid": r["uid"],
                "screen_name": r["username"],
                "pass": r["pass"],
                "ua": r.get("ua"),
                "proxy": get_proxy_by_sid(r.get("proxy")),
                "rs_attempts": r.get("rs_attempts"),
                "rs_next_try": r.get("rs_next_try"),
            }
            for r in rows
        ]

    def get_auth_by_uid(self, uid: str) -> str | None:
        """
        Возвращает auth_token по uid.
        Если запись не найдена — возвращает None.
        """
        sql = """
            SELECT auth_token
            FROM X_FERMA
            WHERE uid = %s
            LIMIT 1
        """

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (uid,))
            row = cur.fetchone()

        if row:
            # row — это dict благодаря row_factory=dict_row
            return row.get("auth_token")

        return None

    def get_working_accounts(
            self,
            count: int | None = None,
            screen_name: str | None = None,
            pw_change_mode: bool = False,
            email_change_mode: bool = False
    ) -> List[dict]:
        """
        Возвращает аккаунты из X_FERMA.

        Если screen_name указан → возвращает конкретный аккаунт,
          игнорируя is_banned / is_influencer / pass_changed.

        Если screen_name НЕ указан → применяется обычная логика выборки рабочих аккаунтов.
          Если pw_change_mode=True → добавляется фильтр pass_changed IS NOT TRUE.
          Если email_change_mode=True → добавляется фильтр email_changed IS NOT TRUE.
        """

        # --- 1. Режим выборки по одному username ---
        if screen_name:
            base_sql = """
                SELECT uid, username AS screen_name, ua, proxy, auth_token, pass
                FROM X_FERMA
                WHERE LOWER(username) = LOWER(%s)
                ORDER BY addition_date DESC
            """
            params = [screen_name]

        # --- 2. Режим обычной выборки аккаунтов ---
        else:
            base_sql = """
                SELECT uid, username AS screen_name, ua, proxy, auth_token, pass
                FROM X_FERMA
                WHERE is_banned IS NOT TRUE
                  AND is_influencer IS NOT TRUE
                  AND is_locked IS NOT TRUE
            """
            params = []

            # Добавляем фильтр pass_changed IS NOT TRUE, если включён режим смены пароля
            if pw_change_mode:
                base_sql += " AND pass_changed IS NOT TRUE"

            # Добавляем фильтр email_changed IS NOT TRUE, если включён режим смены email
            if email_change_mode:
                base_sql += " AND email_changed IS NOT TRUE"

            base_sql += " ORDER BY addition_date DESC"

        # --- 3. Лимит ---
        if count is not None:
            base_sql += " LIMIT %s"
            params.append(count)

        # --- 4. Выполняем запрос ---
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(base_sql, tuple(params))
            rows = cur.fetchall()

        # --- 5. Приводим к нужному формату ---
        return [
            {
                "uid": r["uid"],
                "screen_name": r["screen_name"],
                "ua": r.get("ua"),
                "proxy": get_proxy_by_sid(r.get("proxy")),
                "auth_token": r.get("auth_token"),
                "pass": r["pass"]
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

    # =======================
    #  MAIL_FERMA (основные методы)
    # =======================

    def insert_new_mail(
        self,
        email: str,
        password: str,
        birth_day: int,
        birth_month: int,
        birth_year: int,
        first_name: str,
        last_name: str,
        proxy_sid: str
    ) -> bool:
        """
        Вставка записи в MAIL_FERMA.
        """
        sql = """
        INSERT INTO MAIL_FERMA (email, pass, addition_date, birth_day, birth_month, birth_year, first_name, last_name, proxy_sid)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(sql, (email, password, datetime.now(), birth_day, birth_month, birth_year, first_name, last_name, proxy_sid))
            return True
        except Exception as e:
            return False

    def get_random_mail(self, n=1):
        """
        Возвращает N случайных свободных почт (x_linked IS NOT TRUE)
        """
        sql = """
            SELECT email, pass, proxy_sid
            FROM MAIL_FERMA
            WHERE x_linked IS NOT TRUE
            ORDER BY RANDOM()
            LIMIT %s
        """

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (n,))
            rows = cur.fetchall()

        return [
            {
                "email": r["email"],
                "pass": r["pass"],
                "proxy": get_proxy_by_sid(r["proxy_sid"]),
            }
            for r in rows
        ]

    def update_x_linked(self, mail: str) -> bool:
        sql = "UPDATE MAIL_FERMA SET x_linked = True WHERE LOWER(email) = LOWER(%s) RETURNING email;"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (mail,))
            return cur.fetchone() is not None



if __name__ == '__main__':
    print(get_port())