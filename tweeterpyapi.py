import pickle, json, time
import traceback

from tweeterpy import TweeterPy

from config import parse_accounts_to_list, get_random_mob_proxy, nodemaven_proxy_rotating
from requests.exceptions import ConnectionError, MissingSchema, SSLError, Timeout, ReadTimeout, ProxyError

from database import Database

from concurrent.futures import ThreadPoolExecutor
from math import ceil

db = Database()

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
    proxy = get_proxies_for_twitter_account(acc)
    tw_cl = initialize_client(proxy=proxy)

    if tw_cl:
        tw_cl = load_session(tw_cl, acc["screen_name"])
        # tw_cl.generate_session(acc["auth_token"])
        if tw_cl.logged_in():
            print(f'Account {acc["screen_name"]} successfully logged in!')
        else:
            print(f'Can\'t log in! Account {acc["screen_name"]}')
            time.sleep(3)
            return

        for i in range(2):
            try:
                tw_cl.get_user_data('elonmusk')
                print(f'Account\'s {acc["screen_name"]} session is OK!')
                break
            except ConnectionError:
                trace = traceback.format_exc()
                if 'Connection aborted' in trace and 'Remote end closed connection without response' in trace:
                    print(f'Account\'s {acc["screen_name"]} session is outdated! Trying to generate new session...')
                    new_tw_cl = save_cookies_and_sess(outdated_session=acc)
                    tw_cl = new_tw_cl
                    time.sleep(5)
            except KeyError:
                print(f"Аккаунт {acc['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(acc["uid"])
                except:
                    pass
                return

        acc['session'] = tw_cl
        return acc

    else:
        return


def load_accounts_tweeterpy(mode, how_many_accounts=None, load_cookies=False):
    """
        mode = "set_up" - set up new accounts, parsing file with new data
        mode = "work" - getting working accounts from db
    """

    if mode == 'work':
        twitter_working_accounts = db.get_working_accounts(how_many_accounts)
    elif mode == 'set_up':
        twitter_working_accounts = parse_accounts_to_list()

    if len(twitter_working_accounts) > 10:
        # Прогреваем TweeterPy до многопоточности
        _ = initialize_client(proxy=get_proxies_for_twitter_account(twitter_working_accounts[0]))

    batch_size = 10
    total = len(twitter_working_accounts)
    batches = ceil(total / batch_size)

    for i in range(batches):
        start = i * batch_size
        end = min(start + batch_size, total)
        accounts_batch = twitter_working_accounts[start:end]

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_account, accounts_batch))
            results = [x for x in results if x is not None]

        # Обновляем исходный список (если нужно сохранить сессии обратно)
        twitter_working_accounts[start:end] = results

    if load_cookies:
        for acc in twitter_working_accounts:
            acc['cookies_dict'] = load_cookies_for_twitter_account_from_file(f'x_accs_cookies/{acc["screen_name"]}.json')

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

