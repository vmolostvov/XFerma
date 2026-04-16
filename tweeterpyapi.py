import pickle, json, time, logging, os, inspect
import traceback
import multiprocessing as mp
from tweeterpy import TweeterPy

from config import parse_accounts_to_list, get_random_mob_proxy, nodemaven_proxy_rotating
# from requests.exceptions import ConnectionError, MissingSchema

from curl_cffi.requests.exceptions import ProxyError

from database import Database
from pixelscan_checker import get_proxy_by_sid, generate_valid_sid_nodemaven_proxy

from concurrent.futures import ThreadPoolExecutor
from math import ceil

db = Database()
logger = logging.getLogger("xFerma")
SESS_DIR = 'x_accs_pkl_sessions'

def initialize_client(proxy=None, screen_name=None, max_attempts=3):
    for i in range(max_attempts):
        try:
            return TweeterPy(proxies=proxy)
        except (OSError, ProxyError, ConnectionError) as e:
            logger.warning(f"[INIT] @{screen_name} init fail by specific exc (attempt {i+1}/{max_attempts}) proxy={proxy} err={e}")
            time.sleep(3)
            sid = generate_valid_sid_nodemaven_proxy()
            new_proxy_value = get_proxy_by_sid(sid)
            proxy = new_proxy_value
        except RuntimeError as e:
            trace = traceback.format_exc()
            if 'CONNECT tunnel failed' in trace:
                sid = generate_valid_sid_nodemaven_proxy()
                new_proxy_value = get_proxy_by_sid(sid)
                proxy = new_proxy_value
        except Exception as e:
            trace = traceback.format_exc()
            if 'raise Exception("invalid response")' in trace:
                logger.warning(f"[INIT] @{screen_name} init fail by general exc (attempt {i + 1}/{max_attempts}) proxy={proxy} err={e}")
                time.sleep(3)
                if 'SSLError' not in trace:
                    sid = generate_valid_sid_nodemaven_proxy()
                    new_proxy_value = get_proxy_by_sid(sid)
                    proxy = new_proxy_value

    return None

def load_accounts():
    twitter_working_accounts = parse_accounts_to_list()
    for acc in twitter_working_accounts:
        tw_cl = initialize_client(proxy=get_proxies_for_twitter_account(acc))
        load_session(tw_cl, acc["screen_name"])
        acc['session'] = tw_cl

def _cookies_set_safe(cj, **kwargs):
    """
    Вызывает cj.set(...) только с поддерживаемыми keyword args.
    Работает и для requests-cookiejar, и для curl_cffi cookies.
    """
    fn = cj.set
    try:
        sig = inspect.signature(fn)
        allowed = set(sig.parameters.keys())
    except Exception:
        # если сигнатуру не получить — используем минимальный набор
        allowed = {"name", "value", "domain", "path", "secure"}

    filtered = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    return fn(**filtered)


def _apply_state_to_client(tw_cl, state: dict):
    s = tw_cl.request_client.session

    # headers / proxies
    if hasattr(s, "headers"):
        s.headers.clear()
        s.headers.update(state.get("headers", {}) or {})
    if hasattr(s, "proxies"):
        s.proxies.update(state.get("proxies", {}) or {})

    # cookies
    cj = getattr(s, "cookies", None)
    cookies_full = state.get("cookies_full", []) or []

    if cj is not None and cookies_full:
        if hasattr(cj, "set"):
            for c in cookies_full:
                name = c.get("name")
                value = c.get("value")
                if not name:
                    continue

                # expires кладём только если set() поддерживает (в curl_cffi чаще нет)
                _cookies_set_safe(
                    cj,
                    name=name,
                    value=value,
                    domain=c.get("domain"),
                    path=c.get("path") or "/",
                    secure=bool(c.get("secure", False)),
                    expires=c.get("expires"),  # будет отфильтровано, если не поддерживается
                )

        elif isinstance(cj, dict):
            for c in cookies_full:
                if c.get("name"):
                    cj[c["name"]] = c.get("value", "")

def load_session(tw_cl, session_name: str):
    with open(f"{SESS_DIR}/{session_name}.pkl", "rb") as f:
        state = pickle.load(f)
    _apply_state_to_client(tw_cl, state)
    return tw_cl

def _dump_cookie_full(c):
    # максимум атрибутов, чтобы cookie реально работали
    rest = getattr(c, "rest", None) or getattr(c, "_rest", None) or {}
    if not isinstance(rest, dict):
        rest = {}
    return {
        "name": getattr(c, "name", None),
        "value": getattr(c, "value", None),
        "domain": getattr(c, "domain", None),
        "path": getattr(c, "path", "/"),
        "secure": bool(getattr(c, "secure", False)),
        "expires": getattr(c, "expires", None),
        "rest": rest,
        "version": getattr(c, "version", None),
        "discard": getattr(c, "discard", None),
    }

def _extract_state_from_client(tw_cl=None, save_cookies_mode=False, cj=None) -> dict:
    if not save_cookies_mode:
        s = tw_cl.request_client.session
        headers = dict(getattr(s, "headers", {}) or {})
        proxies = dict(getattr(s, "proxies", {}) or {})
        cj = getattr(s, "cookies", None)

    cookies_full = []
    if cj is not None:
        try:
            for c in cj:
                # если вдруг итерируется строками, пропустим и попробуем другой путь ниже
                if hasattr(c, "name") and hasattr(c, "value"):
                    cookies_full.append(_dump_cookie_full(c))
        except Exception:
            pass

        # fallback: dict cookies
        if not cookies_full and isinstance(cj, dict):
            cookies_full = [{"name": k, "value": v, "domain": ".x.com", "path": "/", "secure": True, "expires": None, "rest": {}} for k, v in cj.items()]

        # fallback: get_dict()
        if not cookies_full and hasattr(cj, "get_dict"):
            try:
                d = cj.get_dict()
                cookies_full = [{"name": k, "value": v, "domain": ".x.com", "path": "/", "secure": True, "expires": None, "rest": {}} for k, v in d.items()]
            except Exception:
                pass
    if not save_cookies_mode:
        return {
            "headers": headers,
            "proxies": proxies,
            "cookies_full": cookies_full,
        }
    else:
        return {'cookies_full': cookies_full}

def save_session(tw_cl, session_name: str):
    os.makedirs(SESS_DIR, exist_ok=True)
    state = _extract_state_from_client(tw_cl)
    with open(f"{SESS_DIR}/{session_name}.pkl", "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)

def save_cookies(screen_name: str, cookie_jar):
    res = _extract_state_from_client(save_cookies_mode=True, cj=cookie_jar)
    cookies_list = res['cookies_full']

    if not cookies_list:
        raise TypeError(f"cookie_jar is not iterable of cookie objects: {type(cookie_jar)}")

    with open(f"x_accs_cookies/{screen_name}.json", "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, ensure_ascii=False, indent=2)

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

# ---------- универсальный раннер в отдельном процессе ----------

def _subprocess_entry(q, func, args, kwargs):
    """Точка входа подпроцесса: вызывает func(*args, **kwargs) и кладёт результат/ошибку в очередь."""
    try:
        val = func(*args, **(kwargs or {}))
        q.put(("ok", val))
    except Exception:
        q.put(("err", traceback.format_exc()))

def run_in_subprocess(target, args=(), kwargs=None, timeout=60):
    """
    Запускает target(*args, **kwargs) в отдельном процессе (spawn).
    Возвращает результат или бросает TimeoutError / RuntimeError.
    """
    if kwargs is None:
        kwargs = {}

    ctx = mp.get_context("spawn")  # кроссплатформенно
    q = ctx.Queue()

    # ЦЕЛЬ — ТОП-ЛЕВЕЛ функция _subprocess_entry
    p = ctx.Process(target=_subprocess_entry, args=(q, target, args, kwargs))
    p.start()
    p.join(timeout)

    if p.is_alive():
        p.terminate()
        p.join(5)
        raise TimeoutError("subprocess timed out")

    if not q.empty():
        status, payload = q.get()
        if status == "ok":
            return payload
        raise RuntimeError(f"child error:\n{payload}")
    raise RuntimeError("child exited without result")


# ---------- воркер: всё опасное — внутри отдельного процесса ----------
def worker_generate_and_save(acc):
    """
    В отдельном процессе:
      - init client (с proxy)
      - generate_session(auth_token)
      - save_session()
      - get_cookies() -> save_cookies()
    Возвращает dict со статусом.
    ВНИМАНИЕ: этот код должен иметь доступ к тем же функциям/импортам:
    initialize_client, get_proxies_for_twitter_account, save_session, save_cookies.
    """
    proxy = get_proxies_for_twitter_account(acc)
    tw_cl = initialize_client(proxy=proxy)
    tw_cl.generate_session(auth_token=acc['auth_token'])
    save_session(tw_cl, acc["screen_name"])
    # tw_cl.save_session(path='x_accs_pkl_sessions', session_name=acc["screen_name"])
    cookies = tw_cl.get_cookies()
    if cookies:
        save_cookies(acc["screen_name"], cookies)
        return {"status": "ok"}
    return {"status": "login_failed"}

def save_cookies_and_sess_with_timeout(outdated_session=None, max_retries=3, timeout_sec=90, retry_sleep=3):
    """
    Делает то же, что твой save_cookies_and_sess, но:
      - гоняет опасные шаги в отдельном процессе,
      - жёсткий таймаут,
      - ретраи.
    Если outdated_session передан — обрабатывает только его и возвращает tw_cl нельзя (непиклимый),
    поэтому возвращаем просто флаг, а после успешной генерации родитель может load_session().
    """
    accounts = [outdated_session] if outdated_session else parse_accounts_to_list()
    last_status = None

    for acc in accounts:
        if 'session' in acc:
            acc.pop('session') # remove session obj to be pickable
        for attempt in range(1, max_retries + 1):
            try:
                res = run_in_subprocess(worker_generate_and_save, args=(acc,), timeout=timeout_sec)
                if res.get("status") == "ok":
                    logger.info(f"[SESS] @{acc['screen_name']} cookies+session saved (attempt {attempt})")
                    last_status = "ok"
                    break
                else:
                    logger.warning(f"[SESS] @{acc['screen_name']} login_failed (attempt {attempt})")
                    last_status = "login_failed"
            except TimeoutError:
                logger.warning(f"[SESS] @{acc['screen_name']} timed out (attempt {attempt}/{max_retries})")
                last_status = "timeout"
            except Exception as e:
                logger.exception(f"[SESS] @{acc['screen_name']} child error on attempt {attempt}: {e}")
                last_status = "error"

            time.sleep(retry_sleep)
        else:
            logger.error(f"[SESS] @{acc['screen_name']} failed after {max_retries} attempts")

    # для случая outdated_session вернём маркер успеха,
    # а саму сессию затем загрузим через load_session() в родительском процессе
    return last_status

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
        session_refreshed = False
        try:
            tw_cl = load_session(tw_cl, acc["screen_name"])
            # tw_cl.load_session(path=f'x_accs_pkl_sessions/{acc["screen_name"]}.pkl')
            if tw_cl.logged_in():
                logger.info(f"[ACC] @{acc['screen_name']} successfully logged in")
            else:
                logger.warning(f"[ACC] Can't log in @{acc['screen_name']}")
                time.sleep(3)
                return {"status": "login_failed", "account": None}
        except AttributeError:
            trace = traceback.format_exc()
            if "'HTMLParserTreeBuilder' object has no attribute 'attribute_dict_class'" in trace:
                logger.warning(f"[ACC] @{acc['screen_name']} session outdated → refreshing…")

                # ВАЖНО: генерацию делаем в отдельном процессе с таймаутом+ретраями
                status = save_cookies_and_sess_with_timeout(
                    outdated_session=acc,
                    max_retries=3,
                    timeout_sec=90,
                    retry_sleep=3
                )
                if status != "ok":
                    logger.error(f"[ACC] refresh session failed for @{acc['screen_name']} (status={status})")
                    return {"status": "conn_error", "account": None}

                # после успешной генерации — перезагружаем сессию из файлов
                tw_cl = load_session(tw_cl, acc["screen_name"])
                session_refreshed = True
                time.sleep(2)

        # for _ in range(100):
        #     try:
        #         tw_cl.get_user_data('elonmusk')
        #         logger.info(f"[ACC] @{acc['screen_name']} session is OK")
        #         break
        #     except (ConnectionError, AttributeError, ReadTimeout, TimeoutError):
        #         trace = traceback.format_exc()
        #         print(trace)
        #         if (('Connection aborted' in trace and 'Remote end closed connection without response' in trace) or
        #                 "'Retry' object has no attribute 'backoff_max'" in trace):
        #             logger.warning(f"[ACC] @{acc['screen_name']} session outdated → refreshing…")
        #
        #             # ВАЖНО: генерацию делаем в отдельном процессе с таймаутом+ретраями
        #             status = save_cookies_and_sess_with_timeout(
        #                 outdated_session=acc,
        #                 max_retries=3,
        #                 timeout_sec=90,
        #                 retry_sleep=3
        #             )
        #             if status != "ok":
        #                 logger.error(f"[ACC] refresh session failed for @{acc['screen_name']} (status={status})")
        #                 return {"status": "conn_error", "account": None}
        #
        #             # после успешной генерации — перезагружаем сессию из файлов
        #             tw_cl = load_session(tw_cl, acc["screen_name"])
        #             session_refreshed = True
        #             time.sleep(2)
        #         else:
        #             if _ == 99:
        #                 logger.exception(f"[ACC] connection error 5 times for @{acc['screen_name']}")
        #                 return {"status": "conn_error", "account": None}
        #             print(f"acc: {acc['screen_name']}; proxy: {acc['proxy']}")
        #             time.sleep(1)
        #     except KeyError:
        #         logger.warning(f"[ACC] @{acc['screen_name']} вероятно забанен")
        #         try:
        #             db.update_is_banned(acc["uid"])
        #         except Exception:
        #             logger.exception("[ACC] update_is_banned failed")
        #         return {"status": "banned", "account": None}

        acc['session'] = tw_cl
        return {"status": "session_refreshed" if session_refreshed else "ok", "account": acc}

    except Exception:
        trace = traceback.format_exc()
        if 'Error code 32 - Could not authenticate you' in trace:
            logger.warning(f"[ACC] @{acc['screen_name']} вероятно забанен")
            try:
                db.update_is_banned(acc["uid"])
            except Exception:
                logger.exception("[ACC] update_is_banned failed")
            return {"status": "banned", "account": None}
        logger.exception(f"[ACC] unexpected error for @{acc.get('screen_name')}")
        return {"status": "init_failed", "account": None}


def load_accounts_tweeterpy(mode, how_many_accounts=None, load_cookies=False, acc_un=None):
    """
    mode = "set_up" - set up new accounts, parsing file with new data
    mode = "work"   - getting working accounts from db
    mode = "test"   - getting working accounts from db for test
    Возвращает список аккаунтов (готовых к работе) и словарь со статистикой.
    """
    if mode == 'work':
        twitter_working_accounts = db.get_working_accounts(how_many_accounts)
    elif mode == 'set_up':
        twitter_working_accounts = parse_accounts_to_list()
    elif mode == 'pw_change':
        twitter_working_accounts = db.get_working_accounts(pw_change_mode=True, screen_name=acc_un, count=how_many_accounts)
    elif mode == 'email_change':
        twitter_working_accounts = db.get_working_accounts(email_change_mode=True, screen_name=acc_un, count=how_many_accounts)
    elif mode == 'test' and acc_un:
        twitter_working_accounts = db.get_working_accounts(screen_name=acc_un)
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

    stats = {
        "total": total,
        "ok": 0,
        "session_refreshed": 0,
        "login_failed": 0,
        "banned": 0,
        "conn_error": 0,
        "init_failed": 0,
    }

    all_ready_accounts = []  # <– сюда собираем только рабочие аккаунты

    for i in range(batches):
        start = i * batch_size
        end = min(start + batch_size, total)
        accounts_batch = twitter_working_accounts[start:end]

        logger.info(f"[LOAD] batch {i + 1}/{batches}: accounts {start + 1}-{end} of {total}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_account, accounts_batch))

        # обновим статистику по батчу
        for r in results:
            stats[r["status"]] = stats.get(r["status"], 0) + 1

        # оставим только успешные и добавим в общий список
        ready_accounts = [r["account"] for r in results if r["account"] is not None]
        all_ready_accounts.extend(ready_accounts)

        logger.info(
            f"[LOAD][batch {i + 1}] ok={sum(1 for r in results if r['status'] == 'ok')} | "
            f"refreshed={sum(1 for r in results if r['status'] == 'session_refreshed')} | "
            f"login_failed={sum(1 for r in results if r['status'] == 'login_failed')} | "
            f"banned={sum(1 for r in results if r['status'] == 'banned')} | "
            f"conn_error={sum(1 for r in results if r['status'] == 'conn_error')} | "
            f"init_failed={sum(1 for r in results if r['status'] == 'init_failed')}"
        )

    # вместо мутирования исходного списка
    twitter_working_accounts = all_ready_accounts

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

    # --- после вывода общей статистики ---
    logger.info("=" * 80)
    logger.info("🧠 [LOAD COMPLETE] Проверка статистики перед запуском фермы")
    logger.info("-" * 80)
    logger.info(f"📊 Всего аккаунтов:        {stats['total']}")
    logger.info(f"✅ Успешно загружено:      {stats['ok']}")
    logger.info(f"♻️  Обновлено сессий:       {stats['session_refreshed']}")
    logger.info(f"⚠️  Ошибок входа:           {stats['login_failed']}")
    logger.info(f"🚫 Забанено:               {stats['banned']}")
    logger.info(f"🌐 Ошибки соединения:       {stats['conn_error']}")
    logger.info(f"💀 Ошибки инициализации:    {stats['init_failed']}")
    logger.info(f"🟩 Готово к работе:         {len(twitter_working_accounts)}")
    logger.info("=" * 80)

    input("\n🔸 Проверь статистику выше и нажми Enter, чтобы запустить ферму... ")
    logger.info("🚀 Запуск фермы...")

    return twitter_working_accounts


def load_accounts_cookies(mode, acc_un=None, how_many_accounts=None):
    if mode == 'all':
        twitter_working_accounts = db.get_working_accounts(how_many_accounts)
    elif mode == 'one' and acc_un:
        twitter_working_accounts = db.get_working_accounts(screen_name=acc_un)
    else:
        twitter_working_accounts = []


    for acc in twitter_working_accounts:
        acc['cookies_dict'] = load_cookies_for_twitter_account_from_file(
            f'x_accs_cookies/{acc["screen_name"]}.json'
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
        except (OSError, ProxyError, ConnectionError):
            logger.exception(f"Account {username}, error {i} with proxy!")
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


def get_user_id_by_sn(sn: str) -> str:
    tw_cl = TweeterPy()
    return tw_cl.get_user_id(sn)

if __name__ == '__main__':
    print(get_user_id_by_sn('elonmusk'))

