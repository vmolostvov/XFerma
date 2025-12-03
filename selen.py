import time, traceback, telebot, logging
from alarm_bot import admin_error
from database import Database
# from seleniumbase import decorators
# from seleniumbase import sb_cdp
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


def login(username, password, proxy):
    logger.info(f"🔐 [LOGIN] Начинаю логин для @{username} | Proxy: {proxy}")

    try:
        with SB(uc=True, xvfb=True, proxy=proxy) as sb:
            logger.debug("[LOGIN] Browser session инициализирована")

            sb.activate_cdp_mode("https://x.com/i/flow/login")
            logger.info("[LOGIN] Открыта страница входа")

            # --- ввод username
            try:
                sb.write("input[name='text']", username, timeout=30)
                logger.info(f"[LOGIN] Ввел username @{username}")
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
                except:
                    pass

                sb.get("https://x.com/home")

                # пытаемся кликнуть в поле твита (признак успешного входа)
                sb.cdp.click('div[aria-label="Post text"]', timeout=10)

                # проверка генерации cookies
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
                web_audit_vip_user_message_with_photo('680688412', 'ss_test.png', f"❌ [LOGIN] Ошибка проверки входа для @{username}")
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
        except:
            if 'PHOTO_INVALID_DIMENSIONS' in traceback.format_exc():
                time.sleep(15)


def main():
    db = Database()
    logger.info("🚀 [REGEN] Запуск мониторинга аккаунтов для регенерации сессий...")

    while True:
        try:
            regen_sess_accs = db.get_regen_sess_accounts()

            if regen_sess_accs:
                logger.info(f"🔄 [REGEN] Найдено аккаунтов для регенерации: {len(regen_sess_accs)}")

                for acc in regen_sess_accs:
                    sn = acc.get("screen_name")
                    uid = acc.get("uid")

                    logger.info(f"➡️  [REGEN] Обработка @{sn} (uid={uid})")

                    try:
                        new_auth_token = login(
                            sn,
                            acc['pass'],
                            acc['proxy']
                        )
                    except Exception as e:
                        logger.exception(f"❌ [REGEN] Ошибка login() для @{sn}: {e}")
                        continue

                    if not new_auth_token:
                        logger.warning(f"⚠️ [REGEN] login() не вернул token для @{sn}")
                        db.increment_rs_attempts(uid)
                        continue

                    # обновляем токен
                    try:
                        db.update_auth(uid, new_auth_token)
                        db.update_regen_session(uid, False)
                        logger.info(f"✅ [REGEN] Обновлен auth_token для @{sn}")
                    except Exception as e:
                        logger.exception(f"❌ [DB] Ошибка update_auth для @{sn}: {e}")
                        continue

                    acc['auth_token'] = new_auth_token

                    # регенерация сессии + cookies
                    try:
                        status = save_cookies_and_sess_with_timeout(outdated_session=acc)
                        if status == "ok":
                            logger.info(f"🍪 [REGEN] Успешно перегенерирована сессия для @{sn}")
                        else:
                            logger.error(f"❌ [REGEN] Ошибка save_cookies_and_sess_with_timeout для @{sn}, статус={status}")
                    except Exception as e:
                        logger.exception(f"❌ [REGEN] Ошибка save_cookies_and_sess_with_timeout() для @{sn}: {e}")

                    time.sleep(10)

            else:
                logger.debug("[REGEN] Нет аккаунтов, требующих регенерации")

        except Exception as e:
            logger.exception(f"🔥 [MAIN] Необработанная ошибка в главном цикле: {e}")



if __name__ == '__main__':
    main()