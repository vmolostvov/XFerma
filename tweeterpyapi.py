import pickle, json, time, logging
import traceback

from tweeterpy import TweeterPy

from config import parse_accounts_to_list, get_random_mob_proxy, nodemaven_proxy_rotating
from requests.exceptions import ConnectionError, MissingSchema, SSLError, Timeout, ReadTimeout, ProxyError

from database import Database

from concurrent.futures import ThreadPoolExecutor
from math import ceil

db = Database()
logger = logging.getLogger("xFerma")

def initialize_client(proxy=None, screen_name=None):
    for i in range(3):
        try:
            return TweeterPy(proxies=proxy)
        except (OSError, ProxyError, ConnectionError, MissingSchema, ReadTimeout):
            print(f"Account {screen_name} got error while initializing the client! Proxy: {proxy}")
            time.sleep(3)
            proxy = get_random_mob_proxy()

def load_accounts():
    twitter_working_accounts = parse_accounts_to_list()
    for acc in twitter_working_accounts:
        tw_cl = initialize_client(proxy=get_proxies_for_twitter_account(acc))
        load_session(tw_cl, acc["screen_name"])
        acc['session'] = tw_cl

def load_session(tw_cl, session_name):
    with open(f"x_accs_pkl_sessions/{session_name}.pkl", "rb") as file:
        tw_cl.request_client = pickle.load(file)

        return tw_cl

def save_session(tw_cl, session_name):
    with open(f"x_accs_pkl_sessions/{session_name}.pkl", "wb") as file:
        pickle.dump(tw_cl.request_client, file)

def save_cookies(cookies_name, cookie_jar):
    """
        Сохраняет cookies из RequestsCookieJar в файл в формате JSON

        :param cookie_jar: Объект RequestsCookieJar с cookies
        :param cookies_name: Путь к файлу для сохранения
        """
    # Преобразуем CookieJar в список словарей
    cookies_list = [
        {"name": cookie.name, "value": cookie.value}
        for cookie in cookie_jar
    ]

    # Записываем в файл с красивым форматированием
    with open(f"x_accs_cookies/{cookies_name}.json", 'w', encoding='utf-8') as f:
        json.dump(cookies_list, f, indent=4, ensure_ascii=False)

def get_proxies_for_twitter_account(twitter_working_account):
    # https://github.com/edeng23/binance-trade-bot/issues/438
    if twitter_working_account['proxy']:
        proxies = {
            "http": f"http://{twitter_working_account['proxy']}",
            "https": f"http://{twitter_working_account['proxy']}"
        }
    else:
        proxies = None
    return proxies

def load_cookies_for_twitter_account_from_file(twitter_cookies_filename):
    with open(twitter_cookies_filename, "r") as f:
        cookies = json.load(f)
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    return cookies_dict

def save_cookies_and_sess(outdated_session=None):
    if outdated_session:
        twitter_working_accounts = [outdated_session]
    else:
        twitter_working_accounts = parse_accounts_to_list()

    for acc in twitter_working_accounts:
        tw_cl = initialize_client(proxy=get_proxies_for_twitter_account(acc))
        tw_cl.generate_session(auth_token=acc['auth_token'])
        save_session(tw_cl, acc["screen_name"])
        cookies_data = tw_cl.get_cookies()
        if cookies_data:
            print(f'Account {acc["screen_name"]} successfully logged in!')
            save_cookies(acc["screen_name"], cookies_data)
        else:
            print(f'Can\'t log in! Account {acc["screen_name"]}')
            time.sleep(3)

    if outdated_session:
        return tw_cl

def process_account(acc):
    """Возвращает dict: {"status": <ok|session_refreshed|login_failed|banned|conn_error|init_failed>, "account": acc_or_None}"""
    try:
        proxy = get_proxies_for_twitter_account(acc)
        tw_cl = initialize_client(proxy=proxy)
    except Exception:
        logger.exception(f"[ACC] init client failed for @{acc.get('screen_name')}")
        return {"status": "init_failed", "account": None}

    if not tw_cl:
        return {"status": "init_failed", "account": None}

    try:
        tw_cl = load_session(tw_cl, acc["screen_name"])
        # tw_cl.generate_session(acc["auth_token"])
        if tw_cl.logged_in():
            logger.info(f"[ACC] @{acc['screen_name']} successfully logged in")
        else:
            logger.warning(f"[ACC] Can't log in @{acc['screen_name']}")
            time.sleep(3)
            return {"status": "login_failed", "account": None}

        session_refreshed = False

        for _ in range(2):
            try:
                tw_cl.get_user_data('elonmusk')
                logger.info(f"[ACC] @{acc['screen_name']} session is OK")
                break
            except ConnectionError:
                trace = traceback.format_exc()
                if 'Connection aborted' in trace and 'Remote end closed connection without response' in trace:
                    logger.warning(f"[ACC] @{acc['screen_name']} session outdated → refreshing…")
                    try:
                        new_tw_cl = save_cookies_and_sess(outdated_session=acc)
                        tw_cl = new_tw_cl
                        session_refreshed = True
                        time.sleep(5)
                    except Exception:
                        logger.exception(f"[ACC] refresh session failed for @{acc['screen_name']}")
                        return {"status": "conn_error", "account": None}
                else:
                    logger.exception(f"[ACC] connection error for @{acc['screen_name']}")
                    return {"status": "conn_error", "account": None}
            except KeyError:
                logger.warning(f"[ACC] @{acc['screen_name']} вероятно забанен")
                try:
                    db.update_is_banned(acc["uid"])
                except Exception:
                    logger.exception("[ACC] update_is_banned failed")
                return {"status": "banned", "account": None}
            # except AttributeError:
            #     trace = traceback.format_exc()
            #     if "'Retry' object has no attribute 'backoff_max'" in trace:
            #         logger.warning(f"[ACC] @{acc['screen_name']} вероятно забанен")
            #         try:
            #             db.update_is_banned(acc["uid"])
            #         except Exception:
            #             logger.exception("[ACC] update_is_banned failed")
            #         return {"status": "banned", "account": None}
            #     else:
            #         logger.exception(f"[ACC] connection error for @{acc['screen_name']}")
            #         return {"status": "conn_error", "account": None}

        acc['session'] = tw_cl
        return {"status": "session_refreshed" if session_refreshed else "ok", "account": acc}

    except Exception:
        logger.exception(f"[ACC] unexpected error for @{acc.get('screen_name')}")
        return {"status": "init_failed", "account": None}


def load_accounts_tweeterpy(mode, how_many_accounts=None, load_cookies=False):
    """
    mode = "set_up" - set up new accounts, parsing file with new data
    mode = "work"   - getting working accounts from db
    Возвращает список аккаунтов (готовых к работе) и словарь со статистикой.
    """
    if mode == 'work':
        twitter_working_accounts = db.get_working_accounts(how_many_accounts)
    elif mode == 'set_up':
        twitter_working_accounts = parse_accounts_to_list()
    else:
        twitter_working_accounts = []

    total = len(twitter_working_accounts)
    if total == 0:
        logger.info("[LOAD] нет аккаунтов для загрузки")
        return []

    # прогрев
    if total > 10:
        try:
            _ = initialize_client(proxy=get_proxies_for_twitter_account(twitter_working_accounts[0]))
        except Exception:
            logger.exception("[LOAD] Warmup client failed")

    batch_size = 10
    batches = ceil(total / batch_size)

    # глобальные счётчики
    stats = {"total": total, "ok": 0, "session_refreshed": 0, "login_failed": 0, "banned": 0, "conn_error": 0, "init_failed": 0}

    # будем заменять элементы исходного списка результатами сессий
    for i in range(batches):
        start = i * batch_size
        end = min(start + batch_size, total)
        accounts_batch = twitter_working_accounts[start:end]

        logger.info(f"[LOAD] batch {i+1}/{batches}: accounts {start+1}-{end} of {total}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_account, accounts_batch))

        # обновим статистику по батчу
        for r in results:
            stats[r["status"]] += 1

        # оставим только успешные (есть account с session)
        ready_accounts = [r["account"] for r in results if r["account"] is not None]

        # запишем обратно в основной список только готовые
        twitter_working_accounts[start:end] = ready_accounts

        logger.info(
            f"[LOAD][batch {i+1}] ok={sum(1 for r in results if r['status']=='ok')} | "
            f"refreshed={sum(1 for r in results if r['status']=='session_refreshed')} | "
            f"login_failed={sum(1 for r in results if r['status']=='login_failed')} | "
            f"banned={sum(1 for r in results if r['status']=='banned')} | "
            f"conn_error={sum(1 for r in results if r['status']=='conn_error')} | "
            f"init_failed={sum(1 for r in results if r['status']=='init_failed')}"
        )

    # сплющим список (после замены батчами могут быть "дыры")
    twitter_working_accounts = [acc for acc in twitter_working_accounts if acc]

    if load_cookies:
        for acc in twitter_working_accounts:
            try:
                acc['cookies_dict'] = load_cookies_for_twitter_account_from_file(
                    f'x_accs_cookies/{acc["screen_name"]}.json'
                )
            except Exception:
                logger.exception(f"[LOAD] cookies load failed for @{acc.get('screen_name')}")

    logger.info(
        f"[LOAD][TOTAL] accounts={stats['total']} | ok={stats['ok']} | refreshed={stats['session_refreshed']} | "
        f"login_failed={stats['login_failed']} | banned={stats['banned']} | conn_error={stats['conn_error']} | "
        f"init_failed={stats['init_failed']} | ready_to_work={len(twitter_working_accounts)}"
    )

    return twitter_working_accounts


# def load_accounts_tweeterpy(mode, load_cookies=False):
#     """
#     mode = "set_up" - set up new accounts, parsing file with new data
#     mode = "work" - getting working accounts from db
#     """
#
#     if mode == 'work':
#         db = Database()
#         twitter_working_accounts = db.get_working_accounts()
#     elif mode == 'set_up':
#         twitter_working_accounts = parse_accounts_to_list()
#
#     for acc in twitter_working_accounts:
#         tw_cl = initialize_client(proxy=get_proxies_for_twitter_account(acc))
#         tw_cl = load_session(tw_cl, acc["screen_name"])
#         if tw_cl.logged_in():
#             print(f'Account {acc["screen_name"]} successfully logged in!')
#         else:
#             print(f'Can\'t log in! Account {acc["screen_name"]}')
#             time.sleep(3)
#
#         acc['session'] = tw_cl
#
#         if load_cookies:
#             acc['cookies'] = load_cookies_for_twitter_account_from_file(f'x_accs_cookies/{acc["screen_name"]}.json')
#
#     return twitter_working_accounts


def get_user_data(username, tw_cl=None):
    if not tw_cl:
        tw_cl = initialize_client(proxy=nodemaven_proxy_rotating)

    user_data = None
    for i in range(3):
        try:
            user_data = tw_cl.get_user_data(username)
            break
        except (OSError, ProxyError, ConnectionError, MissingSchema):
            print(f"Account {username}, error {i} with proxy!")
            time.sleep(3)

    if user_data:
        user_data = {
            'is_def_ava': user_data['legacy']['default_profile_image'], # false if not default
            'description': user_data['legacy']['description'],
            'uid': user_data['rest_id'], # str
            'name': user_data['legacy']['name'],
            'has_banner': True if user_data['legacy'].get('profile_banner_url') else False
        }

    return user_data


if __name__ == '__main__':
    print(save_cookies_and_sess())

