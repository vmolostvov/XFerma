import random
import time
import traceback
import telebot
import logging
import json
import os
import re
from datetime import datetime, timedelta, timezone

from alarm_bot import admin_error
from database import Database
from seleniumbase import SB
from tweeterpyapi import save_cookies_and_sess_with_timeout
from un_generator import generate_unique_outlook_un, get_random_name
from config import generate_password
from pixelscan_checker import generate_valid_sid_nodemaven_proxy
# from ocr import extract_text_easyocr

db = Database()

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

    # fh = logging.FileHandler("loggers/xferma_selen.log", encoding="utf-8")
    # fh.setLevel(logging.INFO)
    # fh.setFormatter(fmt)

    logger.addHandler(ch)
    # logger.addHandler(fh)

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
        with SB(uc=True, proxy=proxy, locale_code='en') as sb:
        # with SB(xvfb=True) as sb:
            logger.debug("[LOGIN] Browser session инициализирована")

            sb.activate_cdp_mode("https://x.com/i/flow/login")

            # sb.open("https://x.com/i/flow/login")
            logger.info("[LOGIN] Открыта страница входа")

            # sb.open("https://api.ipify.org/?format=json")
            # print("IPIFY:", sb.get_text("body"))
            # sb.open("https://ifconfig.me/ip")
            # print("IFCONFIG:", sb.get_text("body"))

            # --- ввод username
            try:
                sb.write("input[name='text']", username, timeout=60)
            except Exception:
                logger.exception(f"❌ [LOGIN] Не удалось ввести username для @{username}")
                sb.cdp.save_screenshot('ss_test.png')
                web_audit_vip_user_message_with_photo(
                    '680688412',
                    'ss_test.png',
                    f"❌ [TEST] Ошибка проверки входа для @{username}"
                )
                return None

            sb.sleep(1)

            # --- кнопка Next
            try:
                next_btn = sb.cdp.find_element("Next", best_match=True)
                next_btn.click()
                # sb.sleep(0.5)
                # sb.cdp.save_screenshot('ss_test.png')
                # web_audit_vip_user_message_with_photo(
                #     '680688412',
                #     'ss_test.png',
                #     f"❌ [TEST] Ошибка проверки входа для @{username}"
                # )
                logger.info("[LOGIN] Нажал кнопку Next")
            except Exception:
                logger.exception(f"❌ [LOGIN] Ошибка клика по кнопке Next для @{username}")
                return None

            sb.sleep(1)

            # --- ввод пароля
            try:
                sb.write("input[name='password']", password, timeout=20)
                logger.info("[LOGIN] Ввел пароль")
                sb.sleep(3)
                sb.cdp.save_screenshot('ss_test.png')
                web_audit_vip_user_message_with_photo(
                    '680688412',
                    'ss_test.png',
                    f"❌ [TEST] Контрольный скрин после ввода пароля для @{username}"
                )
            except Exception:
                logger.exception(f"❌ [LOGIN] Не удалось ввести пароль для @{username}")
                sb.cdp.save_screenshot('ss_test.png')
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
                sb.sleep(1)
                sb.cdp.save_screenshot('ss_test.png')
                web_audit_vip_user_message_with_photo(
                    '680688412',
                    'ss_test.png',
                    f"❌ [TEST] Контрольный скрин после клика на логин для @{username}"
                )
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

                sb.cdp.save_screenshot('ss_test.png')
                web_audit_vip_user_message_with_photo(
                    '680688412',
                    'ss_test.png',
                    f"❌ [TEST] Контрольный скрин для @{username}"
                )

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

                success_users = last_24h.get('success_users', [])
                fail_users = last_24h.get('fail_users', [])
                fail_users = [u for u in fail_users if u not in success_users]


                logger.info(
                    "[REGEN] Нет аккаунтов, требующих регенерации.\n"
                    f"  📆 Сегодня (UTC): success={today.get('success', 0)}, "
                    f"fail={today.get('fail', 0)}\n"
                    f"  ⏱ За последние 24 часа: events={last_24h.get('events', 0)}, "
                    f"distinct_accounts={last_24h.get('distinct_accounts', 0)}\n"
                    f"  ✅ Всего успешных регенов за всё время: {stats.get('total_success', 0)}\n"
                    f"  ❌ Всего неуспешных попыток за всё время: {stats.get('total_fail', 0)}\n"
                    f"  🟢 Успешные за 24ч: {', '.join(success_users) or '—'}\n"
                    f"  🔴 Неуспешные за 24ч: {', '.join(fail_users) or '—'}\n"
                    f"  🕒 Время сейчас (UTC): {datetime.now(timezone.utc)}"
                )

        except Exception as e:
            logger.exception(f"🔥 [MAIN] Необработанная ошибка в главном цикле: {e}")

        time.sleep(30)


def sss(email, pw, alt_mail):
    # proxy = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-3e85cb8c21134-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
    proxy = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-truedexsc-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
    with SB(uc=True, xvfb=True, proxy=proxy, locale_code='en', pls="none") as sb:
        # sb.activate_cdp_mode("https://outlook.live.com/mail/0/?prompt=select_account&deeplink=mail%2F0%2F%3Fnlp%3D0")
        sb.activate_cdp_mode("https://google.com")
        try:
            sb.cdp.click('input[href="/home"]', timeout=3000)
        except:
            pass
        email_input = sb.cdp.wait_for_element_visible('input[id="loginfmt"]', timeout=60)
        email_input.send_keys(email)
        time.sleep(0.5)
        sb.cdp.click('input[type="submit"]')
        pw_input = sb.cdp.wait_for_element_visible('input[id="passwordEntry"]', timeout=60)
        pw_input.send_keys(pw)
        time.sleep(0.5)
        sb.cdp.click('button[type="submit"]')

        try:
            sb.cdp.click('input[href="/home"]', timeout=30)
        except:
            pass

        sb.uc_open_with_cdp_mode('https://account.live.com/password/Change?mkt=en-US&refd=account.microsoft.com&refp=profile')

        for _ in range(2):
            try:
                alt_mail_input = sb.cdp.wait_for_element_visible('input[id="EmailAddress"]', timeout=30)
                alt_mail_input.send_keys(alt_mail)
                time.sleep(0.5)
                sb.cdp.click('input[id="iNext"]')
                break
            except:
                sb.uc_open_with_cdp_mode(
                    'https://account.live.com/password/Change?mkt=en-US&refd=account.microsoft.com&refp=profile')

        code = None
        code_input = sb.cdp.wait_for_element_visible('input[id="iOttText"]', timeout=60)
        code_input.send_keys(code)
        time.sleep(0.5)
        sb.cdp.click('input[id="iNext"]')

        sb.cdp.click('input[href="/home"]', timeout=3000)


# ===============================
#  MAIL_FERMA (new mail creation)
# ===============================

STATS_PATH = "mail_create_stats.json"

def utc_now():
    return datetime.now(timezone.utc)

def load_stats2(path: str = STATS_PATH) -> dict:
    if not os.path.exists(path):
        return {
            "created_success_total": 0,
            "failed_total": 0,
            "events": []  # list of {"ts": "...", "success": bool, "email": str|None, "reason": str|None}
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # если файл битый — не падаем
        return {
            "created_success_total": 0,
            "failed_total": 0,
            "events": []
        }

def save_stats2(stats: dict, path: str = STATS_PATH):
    # оставим только последние N событий, чтобы файл не рос бесконечно
    MAX_EVENTS = 2000
    if len(stats.get("events", [])) > MAX_EVENTS:
        stats["events"] = stats["events"][-MAX_EVENTS:]

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def add_event(stats: dict, success: bool, email: str | None = None, reason: str | None = None):
    stats.setdefault("events", []).append({
        "ts": utc_now().isoformat(),
        "success": bool(success),
        "email": email,
        "reason": reason
    })
    if success:
        stats["created_success_total"] = int(stats.get("created_success_total", 0)) + 1
    else:
        stats["failed_total"] = int(stats.get("failed_total", 0)) + 1

def compute_24h(stats: dict):
    cutoff = utc_now() - timedelta(hours=24)
    events = stats.get("events", [])
    last_24h = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["ts"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= cutoff:
            last_24h.append(e)

    succ_24h = sum(1 for e in last_24h if e.get("success"))
    fail_24h = sum(1 for e in last_24h if not e.get("success"))
    total_24h = succ_24h + fail_24h
    return succ_24h, fail_24h, total_24h, last_24h

def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def log_pretty_stats(logger, stats: dict):
    succ_24h, fail_24h, total_24h, _ = compute_24h(stats)

    logger.info("📊 [MAIL][STATS] Статистика создания аккаунтов")
    logger.info("-" * 70)
    logger.info(f"✅ Успешно создано всего:        {stats.get('created_success_total', 0)}")
    logger.info(f"❌ Неуспешных попыток всего:     {stats.get('failed_total', 0)}")
    logger.info(f"⏱ За последние 24 часа:         success={succ_24h}, fail={fail_24h}, total={total_24h}")
    logger.info(f"🕒 Сейчас (UTC):                 {format_dt(utc_now())}")
    logger.info("-" * 70)

def notify_admin_stub(text: str):
    # TODO: сюда потом вставишь отправку в TG
    # например: tg_bot.send_message(admin_id, text)
    pass

def should_alert(stats: dict) -> tuple[bool, str]:
    """
    Логика "вдруг стало много неуспешных":
    - если за 24ч >= 10 попыток и fail_rate >= 60%
    - ИЛИ если подряд >= 5 фейлов
    """
    succ_24h, fail_24h, total_24h, last_24h = compute_24h(stats)

    # подряд N фейлов (смотрим последние события)
    events = stats.get("events", [])
    streak = 0
    for e in reversed(events[-50:]):
        if e.get("success"):
            break
        streak += 1

    if streak >= 5:
        return True, f"🚨 [MAIL] Подряд {streak} неуспешных попыток создания аккаунта."

    if total_24h >= 10:
        fail_rate = (fail_24h / total_24h) if total_24h else 0
        if fail_rate >= 0.60:
            return True, f"🚨 [MAIL] Высокий процент ошибок за 24ч: {fail_24h}/{total_24h} ({fail_rate:.0%})."

    return False, ""


def create_new_acc(stats_path: str = STATS_PATH):
    stats = load_stats2(stats_path)
    email_un_with_domen = None

    def fail(reason: str):
        add_event(stats, success=False, email=email_un_with_domen, reason=reason)
        save_stats2(stats, stats_path)
        log_pretty_stats(logger, stats)

        alert, msg = should_alert(stats)
        if alert:
            logger.warning(msg)
            notify_admin_stub(msg)

        return False, None

    def ok():
        add_event(stats, success=True, email=email_un_with_domen, reason=None)
        save_stats2(stats, stats_path)
        log_pretty_stats(logger, stats)

        # можно алертить и по успехам, если надо — но обычно нет
        return True, email_un_with_domen

    def is_text_on_ss(given_text):
        ss_fn = 'outlook_captcha_ss.png'
        sb.cdp.save_screenshot(ss_fn)
        ss_text_list = extract_text_easyocr(ss_fn)
        for string in ss_text_list:
            if given_text in string.lower():
                return True
        return False

    def save_cookies(sb, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cookies = sb.get_cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

    while True:

        logger.info("🆕 [MAIL] Начинаю создание нового Outlook аккаунта")

        proxy_sid = generate_valid_sid_nodemaven_proxy()
        proxy = (
            f'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-'
            f'sid-{proxy_sid}-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
        )
        logger.info(f"🌐 [MAIL] Proxy SID={proxy_sid}")

        try:
            with SB(uc=True, xvfb=True, proxy=proxy, locale_code='en', pls="none") as sb:
                sb.activate_cdp_mode('https://signup.live.com/signup')
                logger.info("🌍 [MAIL] Открыта страница регистрации")

                # EMAIL
                try:
                    email_un = generate_unique_outlook_un()
                    email_un_with_domen = email_un + '@outlook.com'
                    sb.write('input[id="floatingLabelInput4"]', email_un_with_domen)
                    sb.sleep(0.5)
                    sb.cdp.click('button[type="submit"]')
                    logger.info(f"📧 [MAIL] Username: {email_un_with_domen}")
                except Exception:
                    logger.exception("❌ [MAIL] Не удалось заполнить email")
                    fail("email_step_failed")
                    sb.cdp.save_screenshot('ss_test.png')
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [MAIL] Ошибка шага email"
                    )
                    continue

                # PASSWORD
                try:
                    email_pw = generate_password()
                    sb.write('input[type="password"]', email_pw)
                    sb.sleep(0.5)
                    sb.cdp.click('button[type="submit"]')
                    logger.info("🔐 [MAIL] Пароль введён")
                except Exception:
                    logger.exception("❌ [MAIL] Не удалось заполнить пароль")
                    fail("password_step_failed")
                    sb.cdp.save_screenshot('ss_test.png')
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [MAIL] Ошибка шага пароля"
                    )
                    continue

                # BIRTH DATE
                try:
                    sb.cdp.gui_click_element('button[name="BirthDay"]')
                    arrow_count = random.randint(1, 28)
                    birth_day = arrow_count + 1
                    for _ in range(arrow_count):
                        sb.cdp.gui_press_key('DOWN')
                    sb.cdp.gui_press_key('ENTER')

                    sb.cdp.click('button[name="BirthMonth"]')
                    arrow_count = random.randint(1, 11)
                    birth_month = arrow_count + 1
                    for _ in range(arrow_count):
                        sb.cdp.gui_press_key('DOWN')
                    sb.cdp.gui_press_key('ENTER')

                    birth_year = random.randint(1970, 2005)
                    sb.write('input[name="BirthYear"]', str(birth_year))
                    sb.sleep(0.5)
                    sb.cdp.click('button[type="submit"]')

                    if 'Enter your birthdate' in sb.get_page_source():
                        logger.warning(f"🎂 [MAIL] BirthDay не введен! Попробуем ввести еще раз...")
                        sb.cdp.gui_click_element('button[name="BirthDay"]')
                        arrow_count = random.randint(1, 28)
                        birth_day = arrow_count + 1
                        for _ in range(arrow_count):
                            sb.cdp.gui_press_key('DOWN')
                        sb.cdp.gui_press_key('ENTER')
                        sb.sleep(0.5)
                        sb.cdp.click('button[type="submit"]')

                    logger.info(f"🎂 [MAIL] Дата рождения: {birth_day}.{birth_month}.{birth_year}")
                except Exception:
                    logger.exception("❌ [MAIL] Ошибка шага даты рождения")
                    fail("birth_step_failed")
                    sb.cdp.save_screenshot('ss_test.png')
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [MAIL] Ошибка шага даты рождения"
                    )
                    continue

                # NAME
                try:
                    first, last = get_random_name()
                    sb.write('input[id="lastNameInput"]', last)
                    sb.sleep(0.5)
                    sb.write('input[id="firstNameInput"]', first)
                    sb.sleep(0.5)
                    sb.cdp.click('button[type="submit"]')
                    logger.info(f"👤 [MAIL] Имя: {first} {last}")
                except Exception:
                    logger.exception("❌ [MAIL] Ошибка шага имени")
                    fail("name_step_failed")
                    sb.cdp.save_screenshot('ss_test.png')
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [MAIL] Ошибка шага имени"
                    )
                    continue

                # CHALLENGE
                try:
                    logger.info("🧩 [MAIL] Проверка challenge")
                    for _ in range(7):
                        try:
                            sb.cdp.click('input[href="/home"]', timeout=6)
                        except Exception:
                            if is_text_on_ss('accessible challenge'):
                                logger.warning("⚠️ [MAIL] accessible challenge")
                                break
                            elif _ == 6:
                                raise
                    sb.cdp.gui_press_key('ENTER')

                    for _ in range(6):
                        try:
                            sb.cdp.click('input[href="/home"]', timeout=10)
                        except Exception:
                            if is_text_on_ss('press again'):
                                logger.warning("⚠️ [MAIL] press again challenge")
                                break
                            elif _ == 6:
                                raise
                    sb.cdp.gui_press_key('ENTER')
                except Exception:
                    logger.exception("❌ [MAIL] Ошибка challenge части")
                    fail("challenge_step_failed")
                    sb.cdp.save_screenshot('ss_test.png')
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [MAIL] Ошибка challenge части"
                    )
                    continue

                # FINAL CHECK
                try:
                    # sb.cdp.wait_for_element_visible('div[id="app-host"]', timeout=40)
                    for i in range(5):
                        sb.sleep(10)
                        url = sb.cdp.get_current_url()
                        if 'privacynotice' not in url and 'ppsecure' not in url:
                            if i ==4:  # chrome-error://chromewebdata ; https://signup.live.com/error.aspx?errcode=
                                print(f"Unexpected final URL: {url}")
                                sb.sleep(5)
                                raise RuntimeError(f"Unexpected final URL: {url}")
                            else:
                                continue
                        elif 'chrome-error' in url:
                            sb.open('https://outlook.live.com/mail/0/')
                            try:
                                sb.cdp.click('input[href="/home"]', timeout=20)
                            except Exception:
                                pass
                            sb.cdp.save_screenshot('ss_test.png')
                            web_audit_vip_user_message_with_photo(
                                '680688412',
                                'ss_test.png',
                                f"❌ [MAIL] chrome-error test"
                            )
                            return
                        break
                    logger.info("✅ [MAIL] Аккаунт успешно создан!")
                except Exception:
                    logger.exception("❌ [MAIL] Финальная проверка провалилась")
                    fail("final_check_failed")
                    sb.cdp.save_screenshot('ss_test.png')
                    web_audit_vip_user_message_with_photo(
                        '680688412',
                        'ss_test.png',
                        f"❌ [MAIL] Ошибка финальной проверки"
                    )
                    continue

                # SAVE TO DB
                try:
                    db.insert_new_mail(
                        email_un_with_domen,
                        email_pw,
                        birth_day,
                        birth_month,
                        birth_year,
                        first,
                        last,
                        proxy_sid
                    )
                    logger.info(f"💾 [MAIL] Сохранено в БД: {email_un_with_domen}")
                except Exception:
                    logger.exception("❌ [MAIL] Не удалось сохранить в БД")
                    fail("db_insert_failed")
                    continue

                # SAVE COOKIES
                try:
                    sb.cdp.save_cookies(file=f"email_cookies/{email_un}.session.dat")
                    logger.info(f"💾 [MAIL] Cookies были успешно сохранены")
                except Exception:
                    logger.exception("❌ [MAIL] Не удалось сохранить cookie")

                ok()

        except Exception:
            logger.exception("🔥 [MAIL] Фатальная ошибка create_new_acc()")
            fail("fatal_exception")
            continue

def get_code_from_email(email, proxy):

    def extract_verification_code(text: str) -> str | None:
        match = re.search(r'\b\d{6}\b', text)
        return match.group() if match else None

    email_un = email.split('@')[0]

    with SB(uc=True, proxy=proxy) as sb:
        cookies_path = f"email_cookies/{email_un}.session.dat"

        sb.activate_cdp_mode("https://outlook.live.com/mail/0/")

        sb.cdp.load_cookies(cookies_path)

        email_el = sb.cdp.select('div[class="S2NDX"]', timeout=30)

        return extract_verification_code(email_el.text)


if __name__ == '__main__':
    # sss('evdokiyabilan1984@outlook.com', 'zA6yyPBQnm', 'galkina_0803@outlook.com')
    login('9835f846c8fa48a', ")j-k)5:5VemNe-;:)$'>", 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-a2f4d7ace4cae-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080')
    # create_new_acc()
    # print(get_code_from_email('a.ballast280@outlook.com', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-49ddd6de7aeaa-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'))