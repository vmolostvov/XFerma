import time
import traceback
import telebot
import logging
import json
from datetime import datetime, timedelta, timezone

from alarm_bot import admin_error
from database import Database
from seleniumbase import SB
from tweeterpyapi import save_cookies_and_sess_with_timeout


# ----------------------------
# ЛОГГЕР (консоль + файл)
# ----------------------------
logger = logging.getLogger("xFerma_selen")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = logging.FileHandler("xferma_selen.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)

# 🔴 ВАЖНО: отключаем проброс в root-логгер
logger.propagate = False

STATS_FILE = "regen_stats.json"


# =========================
#   РАБОТА СО СТАТИСТИКОЙ
# =========================

def load_stats() -> dict:
    """Загрузить статистику из файла или вернуть дефолтную структуру."""
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {
            "total_success": 0,
            "total_fail": 0,
            "events": []  # список событий
        }
    return data


def save_stats(stats: dict) -> None:
    """Сохранить статистику в файл."""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def record_regen_result(screen_name: str, uid: str, result: str, reason: str | None = None):
    """
    Записать результат попытки регена:
      result: 'success' | 'fail_login' | 'fail_session' | 'error'
    reason — необязательное текстовое описание.
    """
    now = datetime.now()
    stats = load_stats()

    stats.setdefault("total_success", 0)
    stats.setdefault("total_fail", 0)
    stats.setdefault("events", [])

    event = {
        "timestamp": now.isoformat(),
        "screen_name": screen_name,
        "uid": uid,
        "result": result
    }
    if reason:
        event["reason"] = reason

    stats["events"].append(event)

    if result == "success":
        stats["total_success"] += 1
    else:
        stats["total_fail"] += 1

    # Обрежем историю, чтобы файл не пух бесконечно (например, 5000 событий)
    MAX_EVENTS = 5000
    if len(stats["events"]) > MAX_EVENTS:
        stats["events"] = stats["events"][-MAX_EVENTS:]

    # ---- Пересчёт агрегатов ----
    # today = по UTC, при желании можно привязать к Moscow/NY и т.д.
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h_cut = now - timedelta(hours=24)

    events = stats["events"]

    # события за сегодня
    events_today = [
        e for e in events
        if datetime.fromisoformat(e["timestamp"]) >= today_start
    ]

    # события за последние 24 часа
    events_24h = [
        e for e in events
        if datetime.fromisoformat(e["timestamp"]) >= last_24h_cut
    ]

    stats["today"] = {
        "success": sum(1 for e in events_today if e["result"] == "success"),
        "fail": sum(1 for e in events_today if e["result"] != "success"),
    }

    stats["last_24h"] = {
        "events": len(events_24h),
        "distinct_accounts": len({e["uid"] for e in events_24h}),
        "success_users": sorted({e["screen_name"] for e in events_24h if e["result"] == "success"}),
        "fail_users": sorted({e["screen_name"] for e in events_24h if e["result"] != "success"}),
    }

    # Можно добавить ещё агрегаты по своему вкусу
    # Например, сколько всего разных аккаунтов мы трогали за всё время:
    stats["all_time_distinct_accounts"] = len({e["uid"] for e in events})

    save_stats(stats)


# =========================
#   ЛОГИН В X/TWITTER
# =========================

def login(username, password, proxy):
    logger.info(f"🔐 [LOGIN] Начинаю логин для @{username} | Proxy: {proxy}")

    try:
        with SB(uc=True, xvfb=True, proxy=proxy) as sb:
            logger.debug("[LOGIN] Browser session инициализирована")

            sb.activate_cdp_mode("https://x.com/i/flow/login")
            logger.info("[LOGIN] Открыта страница входа")

            # --- ввод username
            for i in range(3):
                try:
                    sb.write("input[name='text']", username, timeout=30)
                    logger.info(f"[LOGIN] Ввел username @{username}")
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [TEST] Ошибка проверки входа для @{username}"
                    )
                    sb.sleep(2)
                except Exception:
                    logger.exception(f"❌ [LOGIN] Не удалось ввести username для @{username}")
                    return None

            sb.sleep(1)

            # --- кнопка Next
            try:
                next_btn = sb.cdp.find_element("Next", best_match=True)
                next_btn.click()
                logger.info("[LOGIN] Нажал кнопку Next")
            except Exception:
                logger.exception(f"❌ [LOGIN] Ошибка клика по кнопке Next для @{username}")
                return None

            sb.sleep(1)

            # --- ввод пароля
            try:
                sb.write("input[name='password']", password, timeout=20)
                logger.info("[LOGIN] Ввел пароль")
            except Exception:
                logger.exception(f"❌ [LOGIN] Не удалось ввести пароль для @{username}")
                web_audit_vip_user_message_with_photo(
                    '680688412',
                    'ss_test.png',
                    f"❌ [TEST] Ошибка проверки входа для @{username}"
                )
                return None

            # --- кнопка Log in
            try:
                login_btn = sb.cdp.find_element("Log in", best_match=True)
                login_btn.click()
                logger.info("[LOGIN] Клик по кнопке Log in")
            except Exception:
                logger.exception(f"❌ [LOGIN] Ошибка клика по кнопке Log in для @{username}")
                return None

            # --- Проверка входа
            try:
                sb.cdp.open_new_tab("https://x.com/home")

                try:
                    sb.cdp.click('div[aria-label="Post text"]', timeout=10)
                except Exception:
                    pass

                sb.get("https://x.com/home")

                # небольшой "санити чек": клик по Home
                sb.cdp.click('a[href="/home"]', timeout=30)

                cookies = sb.get_cookies()
                auth_token = next(c['value'] for c in cookies if c['name'] == 'auth_token')

                logger.info(f"✅ [LOGIN] УСПЕХ! @{username} успешно вошёл")
                return auth_token

            except StopIteration:
                logger.error(f"❌ [LOGIN] Не найден auth_token для @{username}")
                return None

            except Exception:
                logger.exception(f"❌ [LOGIN] Ошибка проверки входа для @{username}")
                sb.cdp.save_screenshot('ss_test.png')
                web_audit_vip_user_message_with_photo(
                    '680688412',
                    'ss_test.png',
                    f"❌ [LOGIN] Ошибка проверки входа для @{username}"
                )
                return None

    except Exception:
        trace = traceback.format_exc()
        logger.exception(f"🔥 [LOGIN] Фатальная ошибка login() для @{username}")
        admin_error(trace)
        return None


def web_audit_vip_user_message_with_photo(user, path_to_photo, text):
    WebAuditBot = telebot.TeleBot('6408330846:AAFZLrHOqaTYveAlbeO8CzNdth_fTrbRGac')
    for i in range(3):
        try:
            with open(path_to_photo, 'rb') as photo:
                WebAuditBot.send_photo(user, photo=photo, caption=text, parse_mode='html')
            break
        except Exception:
            if 'PHOTO_INVALID_DIMENSIONS' in traceback.format_exc():
                time.sleep(15)


# =========================
#   MAIN-ЦИКЛ РЕГЕНЕРАЦИИ
# =========================

def regen_auth():
    db = Database()
    logger.info("🚀 [REGEN] Запуск мониторинга аккаунтов для регенерации сессий...")

    # Локальный счётчик успешных регенов за всё время работы скрипта (текущий запуск)
    total_regenerated_run = 0

    while True:
        try:
            regen_sess_accs = db.get_regen_sess_accounts()

            if regen_sess_accs:
                logger.info(f"🔄 [REGEN] Найдено аккаунтов для регенерации: {len(regen_sess_accs)}")

                for acc in regen_sess_accs:
                    sn = acc.get("screen_name")
                    uid = acc.get("uid")

                    logger.info(f"➡️  [REGEN] Обработка @{sn} (uid={uid})")

                    # логин
                    try:
                        new_auth_token = login(sn, acc['pass'], acc['proxy'])
                    except Exception as e:
                        logger.exception(f"❌ [REGEN] Ошибка login() для @{sn}: {e}")
                        record_regen_result(sn, uid, "error", reason="exception_in_login")
                        continue

                    if not new_auth_token:
                        logger.warning(f"⚠️ [REGEN] login() не вернул token для @{sn}")
                        db.increment_rs_attempts(uid)
                        record_regen_result(sn, uid, "fail_login", reason="no_auth_token")
                        continue

                    # обновляем токен
                    try:
                        db.update_auth(uid, new_auth_token)
                        db.update_regen_session(uid, False)
                        logger.info(f"✅ [REGEN] Обновлен auth_token для @{sn}")
                    except Exception as e:
                        logger.exception(f"❌ [DB] Ошибка update_auth для @{sn}: {e}")
                        record_regen_result(sn, uid, "error", reason="db_update_auth_failed")
                        continue

                    acc['auth_token'] = new_auth_token

                    # регенерация сессии + cookies
                    try:
                        status = save_cookies_and_sess_with_timeout(outdated_session=acc)
                        if status == "ok":
                            total_regenerated_run += 1
                            record_regen_result(sn, uid, "success")
                            logger.info(
                                f"🍪 [REGEN] Сессия перегенерирована для @{sn}. "
                                f"Успешно в этом запуске: {total_regenerated_run}"
                            )
                        else:
                            logger.error(
                                f"❌ [REGEN] Ошибка save_cookies_and_sess_with_timeout для @{sn}, статус={status}"
                            )
                            record_regen_result(sn, uid, "fail_session", reason=f"status={status}")
                    except Exception as e:
                        logger.exception(
                            f"❌ [REGEN] Ошибка save_cookies_and_sess_with_timeout() для @{sn}: {e}"
                        )
                        record_regen_result(sn, uid, "error", reason="exception_in_save_cookies")

                    # чтобы не спамить X слишком жёстко
                    time.sleep(120)

            else:
                # Подтягиваем актуальные агрегаты из файла
                stats = load_stats()
                today = stats.get("today", {})
                last_24h = stats.get("last_24h", {})

                logger.info(
                    "[REGEN] Нет аккаунтов, требующих регенерации.\n"
                    f"  📆 Сегодня (UTC): success={today.get('success', 0)}, "
                    f"fail={today.get('fail', 0)}\n"
                    f"  ⏱ За последние 24 часа: events={last_24h.get('events', 0)}, "
                    f"distinct_accounts={last_24h.get('distinct_accounts', 0)}\n"
                    f"  ✅ Всего успешных регенов за всё время: {stats.get('total_success', 0)}\n"
                    f"  ❌ Всего неуспешных попыток за всё время: {stats.get('total_fail', 0)}\n"
                    f"  🟢 Успешные за 24ч: {', '.join(last_24h.get('success_users', [])) or '—'}\n"
                    f"  🔴 Неуспешные за 24ч: {', '.join(last_24h.get('fail_users', [])) or '—'}\n"
                    f"  🕒 Время сейчас (UTC): {datetime.now(timezone.utc)}"
                )

        except Exception as e:
            logger.exception(f"🔥 [MAIN] Необработанная ошибка в главном цикле: {e}")

        time.sleep(30)


def sss(email, pw):
    proxy = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-3e85cb8c21134-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
    with SB(uc=True, xvfb=True, proxy=proxy, locale_code='en') as sb:
        sb.activate_cdp_mode("https://outlook.live.com/mail/0/?prompt=select_account&deeplink=mail%2F0%2F%3Fnlp%3D0")
        email_input = sb.cdp.select('input[name="loginfmt"]', timeout=60)
        email_input.send_keys(email)
        time.sleep(0.5)
        sb.cdp.click('input[type="submit"]')
        pw_input = sb.cdp.select('name[name="passwd"]', timeout=60)
        pw_input.send_keys(pw)
        time.sleep(0.5)
        sb.cdp.click('input[type="submit"]')
        sb.cdp.click('input[href="/home"]', timeout=3000)

if __name__ == '__main__':
    # sss('evdokiyabilan1984@outlook.com', 'zA6yyPBQnm(')
    login('armyjattsunny', 'kvzQStMLnB', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-acbeddd763fd2-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080')